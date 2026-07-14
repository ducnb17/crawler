"""Anti-bot helpers: rotate User-Agent, random delay, và bypass Cloudflare
5s challenge bằng cloudscraper.

Dùng chung cho cả core/fetcher.py (Requests+BS4) và middlewares.py (Scrapy).
"""

import logging
import random
import time

import cloudscraper
import requests

try:
    from fake_useragent import UserAgent

    _ua_generator = UserAgent()
except Exception:  # noqa: BLE001 - fake_useragent có thể lỗi khi không tải được data online
    _ua_generator = None

logger = logging.getLogger(__name__)

# Fallback UA list tĩnh, dùng khi fake_useragent không khởi tạo được (vd: máy
# không có internet lúc build cache lần đầu).
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# Dấu hiệu nhận biết Cloudflare "Just a moment..." / 5s challenge trong HTML.
CLOUDFLARE_MARKERS = (
    "just a moment",
    "cf-chl",
    "cf_chl_opt",
    "challenge-platform",
    "checking your browser before accessing",
)


def get_random_user_agent() -> str:
    """Trả về 1 User-Agent ngẫu nhiên (ưu tiên fake_useragent, fallback list tĩnh)."""
    if _ua_generator is not None:
        try:
            return _ua_generator.random
        except Exception:  # noqa: BLE001
            pass
    return random.choice(FALLBACK_USER_AGENTS)


def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """Sleep ngẫu nhiên trong khoảng [min_seconds, max_seconds] để giả hành vi người dùng."""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug("Random sleep %.2fs", delay)
    time.sleep(delay)


def is_cloudflare_challenge(response) -> bool:
    """Phát hiện response có phải trang Cloudflare challenge không (status 403/503 + marker HTML).

    Hỗ trợ cả requests.Response (status_code, text) và Scrapy Response
    (status, text/body) vì hàm này dùng chung cho core/fetcher.py và
    middlewares.py.
    """
    status = getattr(response, "status_code", None)
    if status is None:
        status = getattr(response, "status", None)
    if status not in (403, 503):
        return False

    text = getattr(response, "text", None)
    if text is None:
        body = getattr(response, "body", b"")
        text = body.decode("utf-8", errors="ignore") if isinstance(body, bytes) else str(body)
    text = (text or "").lower()
    return any(marker in text for marker in CLOUDFLARE_MARKERS)


def fetch(url: str, timeout: int = 30, **kwargs) -> requests.Response:
    """Fetch 1 URL, tự động rotate UA và fallback sang cloudscraper nếu gặp
    Cloudflare challenge.

    kwargs được truyền thẳng vào requests.get/cloudscraper.get (headers bổ
    sung sẽ merge với UA ngẫu nhiên).
    """
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("User-Agent", get_random_user_agent())

    response = requests.get(url, headers=headers, timeout=timeout, **kwargs)

    if is_cloudflare_challenge(response):
        logger.info("Phát hiện Cloudflare challenge tại %s, fallback sang cloudscraper", url)
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        response = scraper.get(url, headers=headers, timeout=timeout, **kwargs)

    return response
