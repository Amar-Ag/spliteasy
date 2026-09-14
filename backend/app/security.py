import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.config import Settings
from app.models import new_id, utcnow

_HASH_ALGORITHM = "pbkdf2_sha256"


def hash_password(password: str, iterations: int) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"{_HASH_ALGORITHM}${iterations}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$")
    except ValueError:
        return False
    if algorithm != _HASH_ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    jti: str
    expires_at: datetime


def create_access_token(user_id: str, settings: Settings) -> str:
    now = utcnow()
    claims = {
        "sub": user_id,
        "jti": new_id(),  # lets logout revoke this token without affecting other sessions
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    """Raises `jwt.PyJWTError` if the token is malformed, forged or expired."""
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "jti", "exp"]},
    )
    return TokenClaims(
        user_id=payload["sub"],
        jti=payload["jti"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )
