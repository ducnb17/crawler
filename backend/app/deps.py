"""FastAPI dependencies: DB session, Redis, current_user, scope checks."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import logger
from app.core.security import extract_subject
from app.models import User

# ===== Common dependencies =====
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ===== Auth =====
def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Authorization scheme")
    token = parts[1].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "empty token")
    return token


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Giải access token → load user từ DB."""
    token = _extract_bearer(authorization)
    try:
        user_id, _email, token_scopes = extract_subject(token)
    except Exception as e:
        logger.debug("token_invalid", error=str(e))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from e
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    # stash scopes cho downstream (mypy: dùng setattr)
    user._token_scopes = token_scopes
    return user


CurrentUser = Annotated[User, Depends(current_user)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


def require_scope(*required: str) -> Any:  # type: ignore[no-untyped-def]
    """Factory dependency: cho phép endpoint nếu user có MỘT trong required scopes
    hoặc là superuser. Cách dùng: `Depends(require_scope("jobs:write"))`."""

    async def _checker(user: CurrentUser) -> User:
        if user.is_superuser:
            return user
        token_scopes: list[str] = list(getattr(user, "_token_scopes", []) or [])
        user_scopes: list[str] = list(user.scopes or [])
        granted = set(token_scopes) & set(user_scopes)
        if not any(s in granted for s in required):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"missing required scope(s): {', '.join(required)}",
            )
        return user

    return _checker


def ensure_owner_filter(user: User, field: str = "owner_id") -> dict[str, object]:
    """Trả về filter dict tôn trọng ownership trừ khi superuser."""
    if user.is_superuser:
        return {}
    return {field: user.id}


async def get_or_404(model: type, db: AsyncSession, item_id: str) -> Any:
    obj: Any = await db.get(model, item_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found")
    return obj


__all__ = [
    "CurrentUser",
    "DbSession",
    "DbSessionDep",
    "current_user",
    "ensure_owner_filter",
    "get_or_404",
    "require_scope",
]
