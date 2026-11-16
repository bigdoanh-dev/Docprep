import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.auth.passwords import hash_password, verify_password
from app.errors import ApiError

DUMMY = hash_password('content-dummy-password-not-an-account')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(conn, actor, action, target, metadata=None):
    from psycopg.types.json import Jsonb
    conn.execute('insert into content_audit_event(actor_id,action,target,metadata) values(%s,%s,%s,%s)',
                 (actor, action, str(target), Jsonb(metadata or {})))


def roles(conn, uid):
    return [r['role'] for r in conn.execute('select role from content_user_role where user_id=%s order by role', (uid,))]


def require(user, role):
    if role not in user['roles']:
        raise ApiError(403, 'forbidden', 'Bạn không có quyền thực hiện thao tác này.')


def issue(conn, user, family=None):
    now, family = datetime.now(timezone.utc), family or uuid4()
    tokens = {k: secrets.token_urlsafe(40) for k in ('access', 'refresh')}
    for kind, token in tokens.items():
        conn.execute('insert into content_token(hash,user_id,kind,family,expires_at) values(%s,%s,%s,%s,%s)',
                     (digest(token), user['id'], kind, family, now + (timedelta(minutes=15) if kind == 'access' else timedelta(days=7))))
    return {'access_token': tokens['access'], 'refresh_token': tokens['refresh'], 'expires_in': 900,
            'roles': roles(conn, user['id']), 'display_name': user['display_name']}


def password_user(conn, username, password):
    user = conn.execute('select * from content_user where username=%s for update', (username.strip().lower(),)).fetchone()
    valid = verify_password(password, user['password_hash'] if user else DUMMY)
    if not user or not user['active'] or not valid:
        raise ApiError(401, 'unauthenticated', 'Tên đăng nhập hoặc mật khẩu không đúng.')
    return user


def login(conn, username, password, ip):
    bucket = digest(ip)
    conn.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))', ('content-login:' + bucket,))
    n = conn.execute("select count(*) n from content_auth_failure where ip_hash=%s and at>now()-interval '15 minutes'", (bucket,)).fetchone()['n']
    if n >= 5:
        raise ApiError(429, 'rate_limited', 'Bạn đã thử quá nhiều lần. Vui lòng thử lại sau.')
    try:
        user = password_user(conn, username, password)
    except ApiError:
        conn.execute('insert into content_auth_failure(ip_hash) values(%s)', (bucket,))
        conn.commit()  # failed login must survive the exception/transaction rollback
        raise
    audit(conn, user['id'], 'login', user['id'])
    return issue(conn, user)


def authenticate(conn, bearer):
    row = conn.execute("""select u.id,u.username,u.display_name,t.family from content_token t join content_user u on u.id=t.user_id
        where t.hash=%s and t.kind='access' and not t.revoked and t.expires_at>now() and u.active""", (digest(bearer),)).fetchone()
    if not row:
        raise ApiError(401, 'unauthenticated', 'Bạn cần đăng nhập vào kho tài liệu.')
    permissions=roles(conn,row['id'])
    if not permissions:
        raise ApiError(403,'forbidden','Tài khoản chưa được cấp quyền content.')
    return {**row, 'roles': permissions}


def create_user(conn, username, password, name, permissions):
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,63}', username) or not 12 <= len(password) <= 1024:
        raise ValueError('Invalid username or password length (12–1024)')
    if not permissions or set(permissions) - {'editor','reviewer','publisher'}:
        raise ValueError('Invalid roles')
    uid = uuid4()
    conn.execute('insert into content_user(id,username,password_hash,display_name) values(%s,%s,%s,%s)',
                 (uid, username, hash_password(password), name))
    for role in set(permissions):
        conn.execute('insert into content_user_role values(%s,%s)', (uid, role))
    audit(conn, uid, 'account_created', uid)
    return uid
