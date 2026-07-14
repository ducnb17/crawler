"""SmartFetcher: flexible HTTP client with two modes and retry backoff.

Modes:
- "standard": plain requests with rotating browser-like headers.
- "anti_cf": cloudscraper, for sites behind a Cloudflare challenge.

Retries with exponential backoff (+ jitter) when the server responds with
HTTP 429 (Too Many Requests) or 503 (Service Unavailable), or when the
connection itself fails/times out.

Run: python -m crawler.core.fetcher (from project root, venv_wsl activated)
"""

import logging
import random
import time

import cloudscraper
import requests
from bs4 import BeautifulSoup

from crawler.utils.user_agents import get_random_header

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = (429, 503)


class SmartFetcher:
    """HTTP client with pluggable fetch mode and automatic retry.

    Args:
        mode: "standard" (requests) or "anti_cf" (cloudscraper).
        max_retries: max retry attempts on 429/503 (or connection errors).
        base_delay: base delay (seconds) used for exponential backoff.
        timeout: request timeout (seconds).
    """

    def __init__(self, mode: str = "standard", max_retries: int = 3, base_delay: float = 1.0, timeout: int = 30):
        if mode not in ("standard", "anti_cf"):
            raise ValueError(f"Unsupported mode: {mode!r}. Use 'standard' or 'anti_cf'.")
        self.mode = mode
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout
        # cloudscraper session được tạo 1 lần và tái sử dụng cho cả đời SmartFetcher.
        self._scraper = None
        if mode == "anti_cf":
            self._scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )

    def _client_get(self, url: str, headers: dict, **kwargs) -> requests.Response:
        """Dispatch GET request tới client tương ứng với mode hiện tại."""
        if self.mode == "anti_cf":
            return self._scraper.get(url, headers=headers, timeout=self.timeout, **kwargs)
        return requests.get(url, headers=headers, timeout=self.timeout, **kwargs)

    def _backoff_delay(self, attempt: int) -> float:
        """Tính delay (giây) cho lần retry thứ `attempt` (0-based) theo Exponential
        Backoff + jitter ngẫu nhiên để tránh nhiều request retry đồng loạt."""
        exp_delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, self.base_delay)
        return exp_delay + jitter

    def get(self, url: str, **kwargs) -> requests.Response:
        """Fetch 1 URL với header ngẫu nhiên hoá, tự retry theo Exponential Backoff
        nếu gặp HTTP 429/503 hoặc lỗi kết nối (timeout, connection error...).

        Trả về requests.Response cuối cùng (đã raise_for_status ở caller nếu cần).
        Raise lại exception nếu hết số lần retry mà vẫn lỗi kết nối.
        """
        headers = kwargs.pop("headers", {}) or {}
        merged_headers = get_random_header()
        # Ép bỏ "br" (Brotli): môi trường không cài brotli/brotlicffi thì
        # requests không tự decode được -> response.text bị garbled.
        merged_headers["Accept-Encoding"] = "gzip, deflate"
        merged_headers.update(headers)

        last_exc = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._client_get(url, merged_headers, **kwargs)
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    logger.error("Fetch %s thất bại sau %d lần thử: %s", url, attempt + 1, exc)
                    raise
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "Lỗi kết nối tới %s (lần %d/%d): %s. Retry sau %.2fs",
                    url, attempt + 1, self.max_retries, exc, delay,
                )
                time.sleep(delay)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "Nhận HTTP %d từ %s (lần %d/%d). Retry sau %.2fs",
                    response.status_code, url, attempt + 1, self.max_retries, delay,
                )
                time.sleep(delay)
                continue

            return response

        # Không nên tới được đây, nhưng đề phòng logic trên đổi trong tương lai.
        if last_exc:
            raise last_exc
        return response


def parse_html(html_content: str) -> dict:
    """Trích xuất dữ liệu cơ bản từ HTML bằng BeautifulSoup4.

    Trả về dict gồm: title, meta_description, và danh sách links (href) đầu
    tiên tìm thấy trên trang.
    """
    soup = BeautifulSoup(html_content, "lxml")

    title_node = soup.find("title")
    title = title_node.get_text(strip=True) if title_node else ""

    meta_desc_node = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_desc_node.get("content", "").strip() if meta_desc_node else ""

    links = [a["href"] for a in soup.find_all("a", href=True)]

    return {
        "title": title,
        "meta_description": meta_description,
        "links": links,
    }


def main():
    """Test nhanh SmartFetcher: gửi request tới 1 trang mẫu và in kết quả parse."""
    test_url = "https://books.toscrape.com/"

    fetcher = SmartFetcher(mode="standard", max_retries=3, base_delay=1.0)
    try:
        response = fetcher.get(test_url)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - chỉ demo, log lỗi rõ ràng thay vì crash
        logger.error("Lỗi khi fetch %s: %s", test_url, exc)
        return

    logger.info("Fetch thành công %s (status=%d)", test_url, response.status_code)

    data = parse_html(response.text)
    logger.info("Title: %s", data["title"])
    logger.info("Meta description: %s", data["meta_description"])
    logger.info("Tìm thấy %d link trên trang.", len(data["links"]))


if __name__ == "__main__":
    main()
