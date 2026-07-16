"""Pydantic schema dùng chung + helpers (timestamp, base model, pagination)."""

from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    """Base model mặc định từ.attributes=True để build từ ORM object."""

    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None


T = TypeVar("T")


class Page[T](BaseModel):
    """Phân trang server-side."""

    items: list[T]
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)


class Message(BaseModel):
    message: str
    detail: str | None = None


class IdResponse(BaseModel):
    id: str
