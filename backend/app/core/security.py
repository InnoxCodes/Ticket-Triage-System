"""Password hashing and JWT issuing/verification.

Uses ``bcrypt`` and ``PyJWT`` directly rather than passlib. Passlib is the
usual recommendation but is effectively unmaintained, and its bcrypt backend
emits a version-detection warning against bcrypt 4.x that people then paper
over. Two small libraries used directly is less code and fewer surprises than
one abstraction over them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings

# bcrypt truncates silently at 72 bytes. Rejecting longer input is better than
# accepting a password whose tail is ignored — otherwise two different long
# passwords can authenticate the same account.
MAX_PASSWORD_BYTES = 72


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, or fails signature checks."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with a per-password salt."""
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # A malformed stored hash must read as "wrong password", never as a
        # 500 — the error path would otherwise distinguish existing accounts
        # from missing ones.
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Issue a signed JWT for ``subject`` (the agent's id, as a string)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "iss": settings.app_name,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT, or raise :class:`InvalidTokenError`.

    ``algorithms`` is pinned to the single configured algorithm. Accepting a
    list the caller does not control is how the classic "alg: none" and
    RS256-downgraded-to-HS256 forgeries work.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
