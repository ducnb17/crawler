"""Downloader middlewares: rotate User-Agent ngẫu nhiên + fallback cloudscraper
khi gặp Cloudflare 5s challenge.

Cả 2 middleware dùng chung helper trong crawler/core/antibot.py để không lặp
logic với core/fetcher.py (nhánh Requests+BS4).
"""

import logging

from scrapy import signals
from scrapy.http import HtmlResponse
from twisted.internet.threads import deferToThread

from crawler.core.antibot import is_cloudflare_challenge
from crawler.utils.user_agents import get_random_user_agent

logger = logging.getLogger(__name__)


class RandomUserAgentMiddleware:
    """Gán 1 User-Agent ngẫu nhiên cho mỗi request (thay UserAgentMiddleware mặc định)."""

    def process_request(self, request, spider):
        request.headers["User-Agent"] = get_random_user_agent()
        return None


class CloudscraperMiddleware:
    """Khi response giống Cloudflare challenge (403/503 + marker HTML), tự
    retry request đó bằng cloudscraper (bypass challenge) thay vì để Scrapy
    downloader mặc định xử lý.

    cloudscraper là thư viện blocking (dựa trên requests), nên phải chạy
    trong thread pool (deferToThread) để không block Twisted reactor.
    """

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider):
        self.logger = spider.logger

    def process_response(self, request, response, spider):
        if request.meta.get("cloudscraper_retry"):
            # Đã retry qua cloudscraper rồi mà vẫn dính challenge -> trả lại
            # response hiện tại, để RetryMiddleware/spider tự quyết định tiếp.
            return response

        if not is_cloudflare_challenge(response):
            return response

        logger.info("Cloudflare challenge tại %s, thử bypass bằng cloudscraper", request.url)
        return deferToThread(self._fetch_with_cloudscraper, request)

    def _fetch_with_cloudscraper(self, request):
        import cloudscraper

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        headers = {k.decode(): v[0].decode() for k, v in request.headers.items()}
        resp = scraper.get(request.url, headers=headers, timeout=30)

        return HtmlResponse(
            url=request.url,
            status=resp.status_code,
            headers=resp.headers,
            body=resp.content,
            encoding="utf-8",
            request=request.replace(meta={**request.meta, "cloudscraper_retry": True}),
        )
