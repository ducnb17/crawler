"""Single source of truth cho User-Agent rotation + header building.

Loại bỏ duplication giữa `utils/user_agents.py` cũ và `core/antibot.py` cũ.
"""

from __future__ import annotations

import random
import re
from typing import Any

from app.config import get_settings
from app.core.logging import logger

# 1 fallback pool chất lượng cao, sẽ dần già nhưng đủ dùng khi fake_useragent fail
STATIC_USER_AGENTS: tuple[str, ...] = (
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
)

ACCEPT_LANGUAGES = ("en-US,en;q=0.9", "en-GB,en;q=0.8", "vi-VN,vi;q=0.9,en;q=0.8", "en;q=0.9")
DEFAULT_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
)

_ua_generator: Any = None
_ua_init_attempted = False


def _init_fake_useragent() -> Any:
    global _ua_generator, _ua_init_attempted
    if _ua_init_attempted:
        return _ua_generator
    _ua_init_attempted = True
    if not get_settings().antibot_use_fake_useragent:
        return None
    try:
        from fake_useragent import UserAgent

        _ua_generator = UserAgent()
        logger.debug("fake_useragent_ready")
    except Exception as e:
        logger.warning("fake_useragent_init_failed", error=str(e))
        _ua_generator = None
    return _ua_generator


def get_random_user_agent() -> str:
    gen = _init_fake_useragent()
    if gen is not None:
        try:
            return str(gen.random)
        except Exception as e:
            logger.debug("fake_useragent_got_exception", error=str(e))
    return random.choice(STATIC_USER_AGENTS)


def _platform_from_ua(ua: str) -> str:
    if "Windows" in ua or "Win64" in ua:
        return '"Windows"'
    if "Macintosh" in ua or "Mac OS X" in ua:
        return '"macOS"'
    if "X11" in ua or "Linux" in ua:
        return '"Linux"'
    if "Android" in ua:
        return '"Android"'
    if "iPhone" in ua or "iPad" in ua:
        return '"iOS"'
    return '"Unknown"'


_CHROME_VER_RE = re.compile(r"Chrome/(\d+)")


def _build_sec_ch_ua(ua: str) -> dict[str, str]:
    m = _CHROME_VER_RE.search(ua)
    if not m:
        return {}  # Firefox/Safari không gửi client hints
    major = m.group(1)
    brand = (
        f'"Microsoft Edge";v="{major}", "Chromium";v="{major}", "Not_A Brand";v="24"'
        if "Edg/" in ua
        else f'"Google Chrome";v="{major}", "Chromium";v="{major}", "Not_A Brand";v="24"'
    )
    return {
        "Sec-Ch-Ua": brand,
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": _platform_from_ua(ua),
    }


def get_random_header() -> dict[str, str]:
    """Headers đầy đủ mô phỏng browser thật. Không dùng br cho Accept-Encoding
    (tránh exception brotli không cài đặt)."""
    ua = get_random_user_agent()
    headers: dict[str, str] = {
        "User-Agent": ua,
        "Accept": DEFAULT_ACCEPT,
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    headers.update(_build_sec_ch_ua(ua))
    return headers
