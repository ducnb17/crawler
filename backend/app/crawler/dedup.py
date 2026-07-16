"""Redis-based dedup theo URL + content hash (xxhash64)."""

from __future__ import annotations

import xxhash

from app.core import redis


def _content_hash(text: str) -> str:
    return xxhash.xxh64(text).hexdigest()


async def is_seen(job_id: str, url: str) -> bool:
    return await redis.set_is_member(f"dedup:{job_id}:url", url)


async def mark_seen(job_id: str, url: str) -> None:
    await redis.set_add(f"dedup:{job_id}:url", url)


async def reset(job_id: str) -> None:
    """Xóa toàn bộ dedup set cho 1 job (khi chạy run mới với force)."""
    r = redis.get_redis()
    await r.delete(redis.ns(f"dedup:{job_id}:url"))
    await r.delete(redis.ns(f"dedup:{job_id}:hash"))


async def is_content_seen(job_id: str, text: str) -> tuple[bool, str]:
    h = _content_hash(text)
    seen = await redis.set_is_member(f"dedup:{job_id}:hash", h)
    return seen, h


async def mark_content_seen(job_id: str, h: str) -> None:
    await redis.set_add(f"dedup:{job_id}:hash", h)
