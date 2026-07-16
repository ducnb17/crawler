"""Auth API: signup, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.core.db import session_scope
from app.deps import CurrentUser
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserRead,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, request: Request) -> TokenPair:
    """Open signup (chỉ cho phép khi env development hoặc first-user)."""
    if not _settings.is_dev:
        # Production: signup chỉ admin qua /users crate. Trừ first-user.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "public signup disabled")
    async with session_scope() as db:
        try:
            user = await auth_service.signup(
                db, email=body.email, password=body.password, full_name=body.full_name
            )
            access, raw, ttl = auth_service.issue_token_pair(user)
            await auth_service.persist_refresh_token(
                db,
                user=user,
                raw_token=raw,
                user_agent=request.headers.get("user-agent"),
                ip=request.client.host if request.client else None,
            )
        except auth_service.EmailAlreadyExistsError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already exists") from e
    return TokenPair(access_token=access, refresh_token=raw, expires_in=ttl)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, request: Request) -> TokenPair:
    async with session_scope() as db:
        try:
            user = await auth_service.authenticate(db, body.email, body.password)
        except auth_service.InvalidCredentialsError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials") from e
        except auth_service.AuthError as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
        access, raw, ttl = auth_service.issue_token_pair(user)
        await auth_service.persist_refresh_token(
            db,
            user=user,
            raw_token=raw,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    return TokenPair(access_token=access, refresh_token=raw, expires_in=ttl)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    async with session_scope() as db:
        try:
            user, new_raw = await auth_service.rotate_refresh_token(db, body.refresh_token)
        except auth_service.InvalidCredentialsError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from e
        except auth_service.AuthError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
        access, _raw, ttl = auth_service.issue_token_pair(user)
        await auth_service.persist_refresh_token(
            db, user=user, raw_token=new_raw, user_agent=None, ip=None
        )
    return TokenPair(access_token=access, refresh_token=new_raw, expires_in=ttl)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(body: LogoutRequest) -> None:
    async with session_scope() as db:
        await auth_service.revoke_refresh_token(db, body.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
