"""Security: JWT (RS256) + password hashing (argon2) + RBAC scopes.

Cách dùng:
- M2 dùng redis + DB trong async; mọi token/refresh token được lưu trong tables.
- Password hash qua passlib CryptContext(schemes=["argon2"]).
- Access Token JWT RS256 signed với private key (PEM), verify với public key.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.core.logging import logger

# ===== Scopes (RBAC) =====
# Quy ước: <resource>:<action> với action ∈ read|write|delete|run|manage
SCOPES: tuple[str, ...] = (
    "jobs:read",
    "jobs:write",
    "jobs:delete",
    "jobs:run",
    "results:read",
    "results:export",
    "results:delete",
    "proxies:read",
    "proxies:write",
    "proxies:delete",
    "webhooks:read",
    "webhooks:write",
    "webhooks:delete",
    "users:read",
    "users:write",
    "users:delete",
    "settings:read",
    "settings:write",
)


class ScopeError(ValueError):
    pass


def validate_scopes(scopes: list[str]) -> list[str]:
    """Loại scope không hợp lệ; trả về list chuẩn hoá."""
    out: list[str] = []
    for raw_scope in scopes:
        scope = raw_scope.strip().lower()
        if scope in SCOPES:
            out.append(scope)
        elif scope == "*":  # superuser-style
            out.extend(SCOPES)
        else:
            logger.warning("invalid_scope_ignored", scope=scope)
    return out


# ===== Password hashing =====
_pwd_ctx = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=2,
)


def hash_password(plain: str) -> str:
    return str(_pwd_ctx.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bool(_pwd_ctx.verify(plain, hashed))
    except Exception as e:
        logger.debug("password_verify_failed", error=str(e))
        return False


# ===== JWT =====
_PRIVATE_KEY: str | None = None
_PUBLIC_KEY: str | None = None


def _read_key(path: str) -> str:
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"JWT key file not found: {path}. Generate with: python -m scripts.gen_jwt_keys"
        )
    return p.read_text(encoding="utf-8")


def get_private_key() -> str:
    global _PRIVATE_KEY
    if _PRIVATE_KEY is None:
        _PRIVATE_KEY = _read_key(get_settings().auth_private_key_path)
    return _PRIVATE_KEY


def get_public_key() -> str:
    global _PUBLIC_KEY
    if _PUBLIC_KEY is None:
        _PUBLIC_KEY = _read_key(get_settings().auth_public_key_path)
    return _PUBLIC_KEY


def create_access_token(
    *,
    user_id: str,
    email: str,
    scopes: list[str],
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Access token JWT ngắn hạn."""
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "scp": scopes,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.auth_access_token_ttl_min)).timestamp()),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return str(jwt.encode(payload, get_private_key(), algorithm="RS256"))


def create_refresh_token_claims(user_id: str) -> dict[str, Any]:
    """Trả về raw claims + token string (token chỉ là opaque value; hash được lưu DB)."""
    s = get_settings()
    now = datetime.now(UTC)
    raw = secrets.token_urlsafe(48)
    expires_at = now + timedelta(days=s.auth_refresh_token_ttl_days)
    return {
        "raw": raw,
        "expires_at": expires_at,
        "token_hash": _hash_token(raw),
    }


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify access token. Raise JWTError nếu invalid."""
    return dict(jwt.decode(token, get_public_key(), algorithms=["RS256"]))


def _hash_token(raw: str) -> str:
    return str(_pwd_ctx.hash(raw))


def verify_refresh_token(raw: str, stored_hash: str) -> bool:
    try:
        return bool(_pwd_ctx.verify(raw, stored_hash))
    except Exception as e:
        logger.debug("refresh_verify_failed", error=str(e))
        return False


# ===== Helpers =====
def token_ttl_seconds() -> int:
    return get_settings().auth_access_token_ttl_min * 60


AccessTokenSubject = tuple[str, str, list[str]]  # (user_id, email, scopes)


def extract_subject(token: str) -> AccessTokenSubject:
    """Trả về (user_id, email, scopes) — raise JWTError nếu token không hợp lệ."""
    claims = decode_access_token(token)
    if claims.get("typ") != "access":
        raise JWTError("not an access token")
    user_id = str(claims["sub"])
    email = str(claims["email"])
    scopes = list(claims.get("scp", []))
    return user_id, email, scopes


def epoch_to_dt(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=UTC)


def now_ts() -> int:
    return int(time.time())


Role = Literal["user", "admin", "superuser"]
