"""Auth service: signup, login, refresh, logout — interact với DB users/refresh_tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token_claims,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.models import RefreshToken, User


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class EmailAlreadyExistsError(AuthError):
    pass


async def signup(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    scopes: list[str] | None = None,
    is_superuser: bool = False,
    make_first_user_superuser: bool = True,
) -> User:
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise EmailAlreadyExistsError(email)
    # First user becomes superuser if env allow
    any_user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
    if make_first_user_superuser and any_user is None:
        is_superuser = True
        scopes = ["*"]  # all scopes
    elif scopes is None:
        scopes = ["jobs:read", "jobs:write", "jobs:run", "results:read", "results:export"]
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_active=True,
        is_superuser=is_superuser,
        scopes=scopes,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.hashed_password:
        raise InvalidCredentialsError()
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise AuthError("user inactive")
    return user


def issue_token_pair(user: User) -> tuple[str, str, int]:
    """Trả về (access_token, refresh_token_raw, access_ttl_seconds)."""
    s = get_settings()
    access_ttl = s.auth_access_token_ttl_min * 60
    scopes = ["*"] if user.is_superuser else (user.scopes or [])
    access_token = create_access_token(user_id=str(user.id), email=user.email, scopes=scopes)
    _rt = create_refresh_token_claims(str(user.id))
    # refresh token sẽ được persist khi caller gọi persist_refresh_token()
    # nhưng ta trả về raw trực tiếp cho caller lưu
    return access_token, _rt["raw"], access_ttl


async def persist_refresh_token(
    db: AsyncSession,
    *,
    user: User,
    raw_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> RefreshToken:
    from app.core.security import _hash_token

    ttl_days = get_settings().auth_refresh_token_ttl_days
    token = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        user_agent=user_agent,
        ip=ip,
    )
    db.add(token)
    await db.flush()
    return token


async def rotate_refresh_token(db: AsyncSession, raw: str) -> tuple[User, str]:
    """Verify refresh token, revoke cũ, cấp mới. Raise AuthError nếu không hợp lệ."""
    # Tìm token có hash matches — scan active refresh tokens (số lượng nhỏ)
    # Cải tiến: lưu hash_idx index prefix nhưng scope M2 giữ đơn giản.
    tokens = (
        (await db.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))))
        .scalars()
        .all()
    )
    matched: RefreshToken | None = None
    for t in tokens:
        if verify_refresh_token(raw, t.token_hash):
            matched = t
            break
    if matched is None:
        raise InvalidCredentialsError()
    if matched.expires_at < datetime.now(UTC):
        # auto-revoke expired
        matched.revoked_at = datetime.now(UTC)
        await db.flush()
        raise AuthError("refresh token expired")
    # Load user
    user = (await db.execute(select(User).where(User.id == matched.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("user not found or inactive")
    # Revoke cũ
    matched.revoked_at = datetime.now(UTC)
    await db.flush()
    # Cấp raw mới
    new_raw = create_refresh_token_claims(str(user.id))["raw"]
    return user, new_raw


async def revoke_refresh_token(db: AsyncSession, raw: str | None) -> None:
    if not raw:
        return
    tokens = (
        (await db.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))))
        .scalars()
        .all()
    )
    for t in tokens:
        if verify_refresh_token(raw, t.token_hash):
            t.revoked_at = datetime.now(UTC)
            await db.flush()
            return


async def revoke_all_for_user(db: AsyncSession, user_id: str) -> int:
    tokens = (
        (
            await db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    for t in tokens:
        t.revoked_at = datetime.now(UTC)
    await db.flush()
    return len(tokens)


__all__ = [
    "AuthError",
    "EmailAlreadyExistsError",
    "InvalidCredentialsError",
    "authenticate",
    "issue_token_pair",
    "persist_refresh_token",
    "revoke_all_for_user",
    "revoke_refresh_token",
    "rotate_refresh_token",
    "signup",
]
