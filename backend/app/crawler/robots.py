"""robots.txt enforcement: parse + cache trong Redis 24h."""

from __future__ import annotations

from urllib.parse import urlparse

from app.core import redis
from app.core.logging import logger

try:
    from robotexclusionrulesparser import RobotExclusionRulesParser

    _rerp_available = True
except Exception:

    class RobotExclusionRulesParser:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.allowed_all = True

        def parse(self, text: str) -> None:
            pass

        def is_allowed(self, ua: str, url: str) -> bool:
            return False

    _rerp_available = False


_CACHE_TTL = 24 * 3600


async def _get_or_load(domain: str) -> RobotExclusionRulesParser:
    r = redis.get_redis()
    key = redis.ns(f"robots:{domain}")
    cached = await r.get(key)
    rerp = RobotExclusionRulesParser()
    if cached:
        rerp.parse(cached)
        return rerp
    # fetch robots.txt
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://{domain}/robots.txt")
            text = resp.text if resp.status_code < 500 else ""
    except Exception as e:
        logger.debug("robots_fetch_failed", domain=domain, error=str(e))
        text = ""
    rerp.parse(text or "")
    await r.set(key, text or "", ex=_CACHE_TTL)
    return rerp


async def is_allowed(url: str, user_agent: str = "*") -> bool:
    """Trả True nếu được phép crawler theo robots.txt."""
    if not _rerp_available:
        return True
    parsed = urlparse(url)
    if not parsed.hostname:
        return True
    try:
        rerp = await _get_or_load(parsed.hostname)
        return bool(rerp.is_allowed(user_agent, url))
    except Exception as e:
        logger.debug("robots_check_failed", url=url, error=str(e))
        return True  # cho phép nếu không parse được


async def reset_cache(domain: str) -> None:
    await redis.get_redis().delete(redis.ns(f"robots:{domain}"))
