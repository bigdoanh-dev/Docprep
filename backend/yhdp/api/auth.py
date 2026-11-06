"""Accounts: scrypt password hashes in `users`, HS256 JWTs signed with a per-install secret."""

import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

import jwt

from yhdp.settings import settings

TOKEN_HOURS = 12
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return hmac.compare_digest(check.hex(), digest)


def jwt_secret(path: Path | None = None) -> str:
    """Created on first use in data/.jwt_secret (owner-only); rotate by deleting the file."""
    path = path or settings.data_dir / ".jwt_secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip()


def make_token(username: str, role: str, secret: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": username, "role": role, "iat": now, "exp": now + TOKEN_HOURS * 3600},
                      secret, algorithm="HS256")


def read_token(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def add_user(con: sqlite3.Connection, username: str, password: str, role: str) -> None:
    with con:
        con.execute("INSERT INTO users (username, pw_hash, role) VALUES (?, ?, ?) "
                    "ON CONFLICT (username) DO UPDATE SET pw_hash = excluded.pw_hash, "
                    "role = excluded.role", (username, hash_password(password), role))


def authenticate(con: sqlite3.Connection, username: str, password: str) -> sqlite3.Row | None:
    row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return row if row and verify_password(password, row["pw_hash"]) else None
