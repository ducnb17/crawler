"""Users API (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.db import session_scope
from app.deps import DbSession, get_or_404, require_scope
from app.models import User
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.schemas.common import Page
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
async def list_users(
    db: DbSession,
    user: User = Depends(require_scope("users:read")),
    page: int = 1,
    size: int = 20,
) -> Page[UserRead]:
    from sqlalchemy import func

    from app.models import User as UserModel

    stmt = select(UserModel)
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    stmt = stmt.order_by(UserModel.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = list((await db.execute(stmt)).scalars().all())
    return Page(
        items=[UserRead.model_validate(r) for r in rows],
        page=page,
        size=size,
        total=total,
        pages=(total + size - 1) // size,
    )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    db: DbSession,
    _: User = Depends(require_scope("users:read")),
) -> UserRead:
    obj = await get_or_404(User, db, user_id)
    return UserRead.model_validate(obj)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    _: User = Depends(require_scope("users:write")),
) -> UserRead:
    async with session_scope() as db:
        try:
            user = await auth_service.signup(
                db,
                email=str(body.email),
                password=body.password,
                full_name=body.full_name,
                scopes=body.scopes,
                is_superuser=body.is_superuser,
                make_first_user_superuser=False,
            )
        except auth_service.EmailAlreadyExistsError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already exists") from e
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    body: UserUpdate,
    _: User = Depends(require_scope("users:write")),
) -> UserRead:
    async with session_scope() as db:
        obj = await get_or_404(User, db, user_id)
        user_obj: User = obj  # type: ignore[assignment]
        if body.full_name is not None:
            user_obj.full_name = body.full_name
        if body.is_active is not None:
            user_obj.is_active = body.is_active
        if body.scopes is not None:
            if not _.is_superuser and "*" in body.scopes:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot grant superuser scope")
            user_obj.scopes = body.scopes
        await db.flush()
    return UserRead.model_validate(user_obj)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_user(
    user_id: str,
    _: User = Depends(require_scope("users:delete")),
) -> None:
    async with session_scope() as db:
        obj = await get_or_404(User, db, user_id)
        user_obj: User = obj  # type: ignore[assignment]
        if user_obj.is_superuser:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot delete superuser")
        await db.delete(obj)
        await db.flush()
