"""Redis client + helpers (distributed lock, set ops, pubsub, frontier)."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Iterable
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings
from app.core.logging import logger

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            encoding="utf-8",
            health_check_interval=30,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def ns(key: str) -> str:
    """Namespace key theo prefix cài đặt."""
    return f"{get_settings().redis_namespace}:{key}"


# ===== Distributed lock =====
class LockNotAcquiredError(RuntimeError):
    pass


class RedisLock:
    """Redis SET NX EX lock với auto-renew (watchdog) tùy chọn."""

    def __init__(self, key: str, ttl: int = 30, acquire_timeout: float = 5.0):
        self.key = ns(f"lock:{key}")
        self.ttl = ttl
        self.acquire_timeout = acquire_timeout
        self._token: str | None = None
        self._renewer: asyncio.Task[None] | None = None

    async def __aenter__(self) -> RedisLock:
        r = get_redis()
        deadline = time.monotonic() + self.acquire_timeout
        while time.monotonic() < deadline:
            self._token = uuid.uuid4().hex
            if await r.set(self.key, self._token, nx=True, ex=self.ttl):
                self._renewer = asyncio.create_task(self._renew_loop())
                return self
            await asyncio.sleep(0.1)
        raise LockNotAcquiredError(self.key)

    async def __aexit__(self, *exc: Any) -> None:
        if self._renewer:
            self._renewer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._renewer
        if self._token:
            r = get_redis()
            # Lua: chỉ DEL nếu token khớp
            await r.eval(
                "if redis.call('GET', KEYS[1]) == ARGV[1] then "
                "return redis.call('DEL', KEYS[1]) else return 0 end",
                1,
                self.key,
                self._token,
            )
        self._token = None

    async def _renew_loop(self) -> None:
        r = get_redis()
        try:
            while True:
                await asyncio.sleep(self.ttl // 3)
                await r.expire(self.key, self.ttl)
        except asyncio.CancelledError:
            pass


# ===== Generic helpers =====
async def set_add(key: str, *values: str) -> int:
    return await get_redis().sadd(ns(key), *values)


async def set_is_member(key: str, value: str) -> bool:
    return bool(await get_redis().sismember(ns(key), value))


async def set_members(key: str) -> set[str]:
    return {v async for v in get_redis().sscan_iter(ns(key))}


async def publish(channel: str, message: str) -> int:
    return await get_redis().publish(ns(channel), message)


async def health() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception as e:
        logger.error("redis_ping_failed", error=str(e))
        return False


async def frontier_push(key: str, urls: Iterable[str], depth: int = 0) -> int:
    """Push vào frontier queue (Redis List, FIFO)."""
    payload = [f"{depth}\x00{u}" for u in urls]
    return await get_redis().rpush(ns(f"frontier:{key}"), *payload) if payload else 0


async def frontier_pop(key: str) -> tuple[str, int] | None:
    """Pop FIFO. Trả về (url, depth) hoặc None nếu rỗng."""
    item = await get_redis().lpop(ns(f"frontier:{key}"))
    if not item or not isinstance(item, str):
        return None
    depth_str, _, url = item.partition("\x00")
    return url, int(depth_str)


async def frontier_len(key: str) -> int:
    return await get_redis().llen(ns(f"frontier:{key}"))
