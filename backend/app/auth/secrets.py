"""Tokens and activation codes. Their values are never stored: only a SHA-256 digest is."""
import hashlib
import secrets
from typing import Literal


def new_token(prefix: Literal["at", "rt"]) -> str:
    """An opaque random token: at_… for access, rt_… for refresh."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_code(code: str) -> str:
    """Digest of an activation code as a person may type it: surrounding spaces and letter case ignored."""
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()
