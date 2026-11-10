"""Sign-in and tokens.

Tokens are opaque random strings; only their digests are stored. The access and refresh token of one
sign-in share a family, so one device can be cut off without touching the others.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4
import re

from app.auth.passwords import hash_password, verify_password
from app.auth.principal import Principal
from app.auth.secrets import hash_code, hash_token, new_token
from app.config import settings
from app.errors import ApiError
from app.repo import auth as auth_repo
from app.repo import consent as consent_repo
from app.repo import learners as learner_repo
from app.repo import staff as staff_repo
from app.repo import credentials


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int   # seconds the access token lives
    family_id: str


def unauthenticated(message_vi: str = "Bạn cần đăng nhập.") -> ApiError:
    return ApiError(401, "unauthenticated", message_vi)


def token_expired() -> ApiError:
    return ApiError(401, "token_expired", "Phiên đăng nhập đã hết hạn.")


def issue_tokens(conn, subject_type: str, subject_id: int, now: datetime, family_id: str | None = None) -> IssuedTokens:
    cfg = settings()["auth"]
    family = family_id or str(uuid4())
    access, refresh = new_token("at"), new_token("rt")
    auth_repo.insert_token(conn, hash_token(access), subject_type, subject_id, "access",
                           now + timedelta(minutes=cfg["access_minutes"]), family, now)
    auth_repo.insert_token(conn, hash_token(refresh), subject_type, subject_id, "refresh",
                           now + timedelta(days=cfg["refresh_days"]), family, now)
    return IssuedTokens(access, refresh, cfg["access_minutes"] * 60, family)


def principal_of(conn, subject_type: str, subject_id: int, family_id: str) -> Principal | None:
    """The caller behind a token, or None when that learner or staff member is gone or inactive."""
    if subject_type == "learner":
        learner = learner_repo.get(conn, subject_id)
        if learner is None or not learner["active"]:
            return None
        return Principal("learner", subject_id, "learner", family_id, learner["pseudonym_id"])
    staff = staff_repo.get(conn, subject_id)
    if staff is None or not staff["active"]:
        return None
    return Principal("staff", subject_id, staff["role"], family_id)


def authenticate(conn, access_token: str | None, now: datetime) -> Principal:
    if not access_token:
        raise unauthenticated()
    token = auth_repo.find_token(conn, hash_token(access_token))
    if token is None or token["kind"] != "access":
        raise unauthenticated()
    if token["revoked_at"] is not None:
        # Replaced by a refresh on this device: the client should retry with its new token, as it
        # does for an expired one. Signed out or cut off: the family has no usable token left.
        raise token_expired() if auth_repo.family_is_live(conn, str(token["family_id"]), now) else unauthenticated()
    if token["expires_at"] <= now:
        raise token_expired()
    principal = principal_of(conn, token["subject_type"], token["subject_id"], str(token["family_id"]))
    if principal is None:
        raise unauthenticated()
    return principal


# ---- signing in ------------------------------------------------------------------------------

def _token_pair(issued: IssuedTokens, role: str, consent_required: bool) -> dict:
    return {"access_token": issued.access_token, "refresh_token": issued.refresh_token,
            "expires_in": issued.expires_in, "role": role, "consent_required": consent_required}


def _consent_required(conn, learner_id: int) -> bool:
    return not consent_repo.has_current_service_consent(conn, learner_id, settings()["consent"]["version"])


def _check_rate_limit(conn, ip: str, kind: str, now: datetime) -> None:
    """Too many failed sign-ins from this address: refuse every attempt, right ones too, until the window passes."""
    # PostgreSQL serializes this bucket across Business replicas; parallel guesses
    # must not all observe the same old failure count.
    conn.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", ("auth:" + kind + ":" + ip,))
    cfg = settings()["auth"]
    since = now - timedelta(minutes=cfg["failure_window_minutes"])
    if auth_repo.count_failures(conn, ip, kind, since) >= cfg["max_failures"]:
        raise ApiError(429, "rate_limited", "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau.")


def _fail(conn, ip: str, kind: str, now: datetime, message_vi: str) -> ApiError:
    """Record a failed sign-in and return the error to raise. The record is committed here: the
    request ends in an error, which would otherwise roll it back. Nothing else may have been written
    in this transaction before this point, or it would be committed too."""
    auth_repo.record_failure(conn, ip, kind, now)
    conn.commit()
    return unauthenticated(message_vi)


WRONG_CODE = "Mã kích hoạt không đúng."


def activate(conn, code: str, ip: str, now: datetime) -> dict:
    """Sign a learner in with their activation code. The first use of a code creates the learner."""
    _check_rate_limit(conn, ip, "activate", now)
    row = auth_repo.find_activation_code(conn, hash_code(code))
    if row is None:
        raise _fail(conn, ip, "activate", now, WRONG_CODE)
    if row["learner_id"] is None:
        cfg = settings()
        learner_id = learner_repo.create(
            conn, learner_repo.next_pseudonym(conn), row["organisation_id"], row["audience"], cfg["exam_date"],
            cfg.get("fsrs", {}).get("desired_retention", 0.9), row["display_name"] or "Học viên")
        auth_repo.bind_activation_code(conn, row["id"], learner_id, now)
    else:
        learner = learner_repo.get(conn, row["learner_id"])
        if learner is None or not learner["active"]:
            raise _fail(conn, ip, "activate", now, WRONG_CODE)   # a closed account answers as an unknown code
        learner_id = learner["id"]
    issued = issue_tokens(conn, "learner", learner_id, now)
    return _token_pair(issued, "learner", _consent_required(conn, learner_id))


def refresh(conn, refresh_token: str, now: datetime) -> dict:
    """Exchange a refresh token for a new pair in the same family. A refresh token presented a second
    time means it leaked: the whole family is revoked. The token's row is locked first, so two
    requests with the same token cannot both be the first."""
    digest = hash_token(refresh_token)
    token = auth_repo.find_token(conn, digest)
    if token and token["subject_type"] == "learner":
        # Same lock as password reset, before the token row: a refresh cannot
        # publish a new session from an old password after a concurrent reset.
        conn.execute("select pg_advisory_xact_lock(71103, %s)", (token["subject_id"],))
    token = auth_repo.find_token(conn, digest, lock=True)
    if token is None or token["kind"] != "refresh":
        raise unauthenticated()
    family = str(token["family_id"])
    if token["revoked_at"] is not None:
        auth_repo.revoke_family(conn, family, now)
        conn.commit()   # keep the revocation although the request ends in an error; nothing else was written
        raise unauthenticated()
    if token["expires_at"] <= now:
        raise token_expired()
    principal = principal_of(conn, token["subject_type"], token["subject_id"], family)
    if principal is None:
        raise unauthenticated()
    auth_repo.revoke_family(conn, family, now)
    issued = issue_tokens(conn, principal.subject_type, principal.subject_id, now, family_id=family)
    needs_consent = principal.subject_type == "learner" and _consent_required(conn, principal.subject_id)
    return _token_pair(issued, principal.role, needs_consent)


def logout(conn, principal: Principal, now: datetime) -> None:
    """Sign this device out; the person's other devices stay signed in."""
    auth_repo.revoke_family(conn, principal.family_id, now)


# ---- staff -----------------------------------------------------------------------------------

STAFF_ROLES = ("reviewer", "admin", "ministry_viewer")
MIN_PASSWORD_LENGTH = 12
WRONG_LOGIN = "Email hoặc mật khẩu không đúng."
# A real hash of a random value, checked when the e-mail is unknown.
_NO_ACCOUNT_HASH = hash_password(new_token("at"))


def normal_username(username: str) -> str:
    value = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", value):
        raise ValueError("username must be 3-64 ASCII letters, digits, dot, underscore or hyphen; start with a letter/digit")
    return value


def set_learner_credentials(conn, learner_id: int, username: str, password: str) -> None:
    """Operator-only binding to an existing learner; never replace another account."""
    username = normal_username(username)
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > 1024:
        raise ValueError("the password needs 12-1024 characters")
    conn.execute("select pg_advisory_xact_lock(71103, %s)", (learner_id,))
    learner_repo.lock(conn, learner_id)
    learner = learner_repo.get(conn, learner_id)
    if not learner or not learner["active"]:
        raise ValueError("learner not found or inactive")
    if credentials.by_learner(conn, learner_id) or credentials.by_username(conn, username):
        raise ValueError("learner or username already has credentials; use reset-learner-password")
    credentials.create(conn, learner_id, username, hash_password(password))


def create_password_learner(conn, username: str, password: str, display_name: str,
                            audience: str = "student") -> int:
    # Validate before creating a learner. CLI wraps creation and credentials in one transaction.
    username = normal_username(username)
    if not display_name.strip() or audience not in ("student", "graduate"):
        raise ValueError("a display name and valid audience are required")
    if not MIN_PASSWORD_LENGTH <= len(password) <= 1024:
        raise ValueError("the password needs 12-1024 characters")
    if credentials.by_username(conn, username):
        raise ValueError("username already exists")
    cfg = settings()
    learner_id = learner_repo.create(conn, learner_repo.next_pseudonym(conn), None, audience, cfg["exam_date"],
                                     cfg.get("fsrs", {}).get("desired_retention", .9), display_name.strip())
    set_learner_credentials(conn, learner_id, username, password)
    return learner_id


def reset_learner_password(conn, username: str, password: str, now: datetime) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= 1024:
        raise ValueError("the password needs 12-1024 characters")
    row = credentials.by_username(conn, normal_username(username))
    if not row:
        raise ValueError("learner account not found")
    conn.execute("select pg_advisory_xact_lock(71103, %s)", (row["learner_id"],))
    learner_repo.lock(conn, row["learner_id"])
    if not credentials.by_username(conn, row["username"]):
        raise ValueError("learner account not found")
    credentials.change_password(conn, row["learner_id"], hash_password(password), now)
    # Mark every old session revoked so already-issued access and refresh tokens stop working.
    auth_repo.revoke_subject(conn, "learner", row["learner_id"], now)


def password_login(conn, username: str, password: str, ip: str, now: datetime) -> dict:
    """Unified form: staff email or a private learner username. Role always comes from the DB."""
    username = username.strip().lower()
    if "@" in username:
        return staff_login(conn, username, password, ip, now)
    _check_rate_limit(conn, ip, "learner_login", now)
    row = credentials.by_username(conn, username)
    learner = None
    if row:
        conn.execute("select pg_advisory_xact_lock(71103, %s)", (row["learner_id"],))
        learner_repo.lock(conn, row["learner_id"])
        learner = learner_repo.get(conn, row["learner_id"])
        row = credentials.by_username(conn, username)
    matches = verify_password(password, row["password_hash"] if row else _NO_ACCOUNT_HASH)
    if not row or not learner or not learner["active"] or not matches:
        raise _fail(conn, ip, "learner_login", now, "Tên đăng nhập hoặc mật khẩu không đúng.")
    issued = issue_tokens(conn, "learner", learner["id"], now)
    return _token_pair(issued, "learner", _consent_required(conn, learner["id"]))


def _normal_email(email: str) -> str:
    return email.strip().lower()


def create_staff(conn, email: str, password: str, display_name: str, role: str) -> int:
    if role not in STAFF_ROLES:
        raise ValueError(f"role must be one of {', '.join(STAFF_ROLES)}; got {role!r}")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"the password needs at least {MIN_PASSWORD_LENGTH} characters")
    return staff_repo.create(conn, _normal_email(email), hash_password(password), display_name.strip(), role)


def staff_login(conn, email: str, password: str, ip: str, now: datetime) -> dict:
    """Sign a staff member in. An unknown e-mail, a closed account and a wrong password are answered
    alike, so the reply does not reveal which accounts exist."""
    _check_rate_limit(conn, ip, "staff_login", now)
    staff = staff_repo.find_by_email(conn, _normal_email(email))
    # Verify even when there is no such account, so both cases take about as long.
    matches = verify_password(password, staff["password_hash"] if staff else _NO_ACCOUNT_HASH)
    if staff is None or not staff["active"] or not matches:
        raise _fail(conn, ip, "staff_login", now, WRONG_LOGIN)
    issued = issue_tokens(conn, "staff", staff["id"], now)
    return _token_pair(issued, staff["role"], False)
