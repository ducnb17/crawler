"""User-Agent helper: danh sách UA tĩnh (Chrome/Firefox/Edge/Safari - Desktop)
kèm tích hợp fake_useragent làm phương án chính.

Dùng get_random_header() để lấy 1 dict header HTTP đầy đủ và ngẫu nhiên hoá
(User-Agent, Accept, Accept-Language, Sec-Ch-Ua...) cho các request antibot.
"""

import logging
import random
import re

try:
    from fake_useragent import UserAgent

    _ua_generator = UserAgent()
except Exception:  # noqa: BLE001 - fake_useragent có thể lỗi khi không tải được data
    _ua_generator = None

logger = logging.getLogger(__name__)

# Danh sách UA tĩnh dùng làm fallback khi fake_useragent không khởi tạo được
# hoặc lúc random bị lỗi. Bao phủ Chrome/Firefox/Edge/Safari trên
# Windows/macOS/Linux, cập nhật các version phổ biến gần đây.
STATIC_USER_AGENTS = [
    # Chrome - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome - Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Firefox - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Firefox - Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Edge - Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    # Edge - macOS

    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    # Safari - macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

# Danh sách Accept-Language phổ biến để random hoá cùng UA.
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,vi;q=0.8",
]

DEFAULT_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)


def get_random_user_agent() -> str:
    """Trả về 1 User-Agent ngẫu nhiên.

    Ưu tiên fake_useragent (dữ liệu UA thực tế, cập nhật online); nếu chưa
    khởi tạo được hoặc random bị lỗi thì fallback sang STATIC_USER_AGENTS.
    """
    if _ua_generator is not None:
        try:
            return _ua_generator.random
        except Exception:  # noqa: BLE001
            logger.debug("fake_useragent.random lỗi, fallback sang static list", exc_info=True)
    return random.choice(STATIC_USER_AGENTS)


def _build_sec_ch_ua(user_agent: str) -> dict:
    """Suy ra các header Sec-Ch-Ua* (Chromium User-Agent Client Hints) từ UA.

    Firefox/Safari không hỗ trợ Sec-Ch-Ua nên trả về dict rỗng cho các UA đó.
    """
    match = re.search(r"Chrome/(\d+)", user_agent)
    if not match:
        return {}

    major_version = match.group(1)
    is_edge = "Edg/" in user_agent
    platform = "Windows"
    if "Macintosh" in user_agent:
        platform = "macOS"
    elif "Linux" in user_agent or "X11" in user_agent:
        platform = "Linux"

    brand = "Microsoft Edge" if is_edge else "Google Chrome"
    sec_ch_ua = (
        f'"Not/A)Brand";v="8", "Chromium";v="{major_version}", '
        f'"{brand}";v="{major_version}"'
    )

    return {
        "Sec-Ch-Ua": sec_ch_ua,
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": f'"{platform}"',
    }


def get_random_header() -> dict:
    """Trả về 1 dict header HTTP hoàn chỉnh, ngẫu nhiên hoá cho mỗi request.

    Bao gồm User-Agent, Accept, Accept-Language, Accept-Encoding và (nếu UA
    là Chromium-based) các header Sec-Ch-Ua* tương ứng - giúp request giống
    browser thật hơn khi crawl.
    """
    user_agent = get_random_user_agent()

    headers = {
        "User-Agent": user_agent,
        "Accept": DEFAULT_ACCEPT,
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    headers.update(_build_sec_ch_ua(user_agent))
    return headers


