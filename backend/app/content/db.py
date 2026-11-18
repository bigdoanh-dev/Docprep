"""Separate SQL migration chain and connection pool for the authoring database."""
import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from urllib.parse import urlsplit

SCHEMA = Path(__file__).resolve().parents[2] / 'content_migrations'


def validate_url(url):
    if not urlsplit(url).path.lstrip('/').startswith('content_'):
        raise RuntimeError('CONTENT_DATABASE_URL must name a dedicated content_* database')
    return url


def connect():
    url = validate_url(os.environ['CONTENT_DATABASE_URL'])
    return psycopg.connect(url, row_factory=dict_row)


def migrate():
    with connect() as conn:
        conn.execute('select pg_advisory_xact_lock(7419001)')
        if not conn.execute("select to_regclass('public.content_schema_version') v").fetchone()['v']:
            conn.execute((SCHEMA / '0001.sql').read_text(encoding='utf-8'))
        current=conn.execute('select max(version) version from content_schema_version').fetchone()['version']
        for path in sorted(SCHEMA.glob('*.sql')):
            if int(path.stem)>current:
                conn.execute(path.read_text(encoding='utf-8'))
        check_ready(conn)
        conn.execute("""revoke create on schema public from public;
            grant usage on schema public to content_app;
            grant select,insert,update on all tables in schema public to content_app;
            grant usage,select on all sequences in schema public to content_app;
            revoke insert,update on content_schema_version from content_app;
            revoke update on source_document_revision,source_asset,document_chunk,taxonomy_snapshot,taxonomy_issue,
              taxonomy_domain,chunk_tag_set,chunk_issue_tag,chunk_domain_tag,chunk_review_decision,content_audit_event from content_app;""")


def check_ready(conn):
    if conn.execute('select max(version) version from content_schema_version').fetchone()['version'] != 4:
        raise RuntimeError('Content schema is not ready')
