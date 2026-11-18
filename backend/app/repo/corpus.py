"""Release pin carried by a worker context, never mutable global configuration."""
import os
from contextvars import ContextVar
from contextlib import contextmanager
from app.config import settings
from app.errors import ApiError

_version=ContextVar('corpus_version',default=None)
_index=ContextVar('corpus_index',default=False)


def selected(conn):
    row=conn.execute('''select r.version,r.status from corpus_activation a join corpus_release r on r.id=a.release_id
        where a.channel=%s''',(os.environ.get('CONTENT_CORPUS_CHANNEL','local'),)).fetchone()
    if row and row['status']!='ready':
        raise ApiError(503,'corpus_revoked','Release đang chọn đã bị thu hồi hoặc chưa sẵn sàng.')
    return row['version'] if row else settings()['corpus_version']


def scope(conn,version=None,index=None):
    v=version or _version.get() or selected(conn)
    conn.execute("select set_config('app.corpus_version',%s,true),set_config('app.corpus_index',%s,true)",
                 (v,'on' if (index if index is not None else _index.get()) else 'off'))
    return v


@contextmanager
def pinned(version,index=False):
    a=_version.set(version);b=_index.set(index)
    try:yield
    finally:_version.reset(a);_index.reset(b)


def unverified_allowed():
    """Explicit dev/test opt-in to call a real model on an unsigned local_dev release. Off by default;
    has no effect outside APP_ENV=dev/test."""
    return os.environ.get('APP_ENV') in ('dev','test') and os.environ.get('PHASE_ALLOW_UNVERIFIED_CORPUS')=='1'


def recheck(conn,version,provider=None,lock=False):
    if lock:
        conn.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('corpus:'+version,))
    row=conn.execute('select trust,status from corpus_release where version=%s',(version,)).fetchone()
    if row and row['status']=='revoked':
        raise ApiError(409,'corpus_revoked','Nguồn của lượt AI đã bị thu hồi.')
    if provider in ('ollama','anthropic','google') and row and row['trust']!='verified' and not unverified_allowed():
        raise ApiError(503,'corpus_not_verified','Nguồn local chưa được xác minh để gọi model thật.')
    if os.environ.get('APP_ENV') not in ('dev','test') and (not row or row['trust']!='verified'):
        raise ApiError(503,'corpus_not_verified','Cần gói nguồn đã được xác minh.')
