"""Tất cả spider của project, gộp từ base_spider.py + generic_spider.py.

- BaseSpider: spider mẫu để test nhanh middleware anti-ban
  (RandomUserAgentMiddleware + CloudscraperMiddleware) mà không phụ thuộc
  config.yaml như GenericSpider.
- GenericSpider: spider tổng quát, đọc start_urls/selector từ config.yaml,
  parse HTML tĩnh, tự fallback sang scrapy-playwright nếu HTML thô gần như
  rỗng/thiếu nội dung mong đợi (dấu hiệu trang cần render JS).
"""

import os
from datetime import datetime, timezone

import scrapy
import yaml

from crawler.items import CrawlerItem

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

# Ngưỡng độ dài text (ký tự) để coi trang là "gần như rỗng".
MIN_CONTENT_LENGTH = 200


def load_config():
    """Đọc config.yaml, trả về dict rỗng nếu file trống/không tồn tại."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class BaseSpider(scrapy.Spider):
    """Spider mẫu: crawl quotes.toscrape.com, extract quote + author.

    Dùng để kiểm tra nhanh:
    - User-Agent có được rotate mỗi request không (xem log DEBUG hoặc header
      gửi đi qua RandomUserAgentMiddleware).
    - CloudscraperMiddleware có tự kích hoạt khi gặp Cloudflare challenge
      không (site test này không có Cloudflare nên bình thường sẽ không
      trigger, nhưng middleware vẫn chạy qua process_response mỗi request).

    Chạy thử:
        scrapy crawl base_spider -o /tmp/base_spider_output.jsonl

    Site test: https://quotes.toscrape.com/ (sandbox scraping công khai, an
    toàn để verify pipeline + middleware trước khi áp dụng cho site thật).
    """

    name = "base_spider"
    allowed_domains = ["quotes.toscrape.com"]
    start_urls = ["https://quotes.toscrape.com/"]

    def parse(self, response):
        now = datetime.now(timezone.utc).isoformat()

        for quote_node in response.css("div.quote"):
            item = CrawlerItem()
            item["url"] = response.url
            item["title"] = quote_node.css("small.author::text").get(default="").strip()
            item["content"] = quote_node.css("span.text::text").get(default="").strip()
            item["crawled_at"] = now
            yield item

        next_href = response.css("li.next a::attr(href)").get()
        if next_href:
            yield response.follow(next_href, callback=self.parse)


class GenericSpider(scrapy.Spider):
    """Spider tổng quát: crawl start_urls từ config.yaml, extract title/content
    theo CSS selector, tự fallback Playwright nếu HTML tĩnh thiếu nội dung."""

    name = "generic_spider"

    # Bật scrapy-playwright handler cho HTTP/HTTPS, chỉ dùng khi request
    # có meta={"playwright": True} (request thường vẫn đi qua downloader thông thường).
    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    }

    def __init__(self, *args, start_url=None, allowed_domain=None,
                 css_selector=None, **kwargs):
        super().__init__(*args, **kwargs)
        config = load_config()

        # Tham số truyền qua `-a` (vd: scrapy crawl generic_spider -a
        # start_url=... -a allowed_domain=... -a css_selector=...) được ưu
        # tiên hơn config.yaml, để backend/app.py có thể chạy crawl theo
        # đúng cấu hình Frontend gửi lên mà không cần ghi đè config.yaml.
        self.start_urls = [start_url] if start_url else config.get("start_urls", [])
        self.allowed_domains = [allowed_domain] if allowed_domain else config.get("allowed_domains", [])
        self.content_selector = css_selector or config.get("content_selector", "body")

        # Selector CSS để lấy title/content, có default hợp lý nếu config thiếu.
        self.title_selector = config.get("title_selector", "title::text")
        # Số trang tối đa sẽ follow qua phân trang (li.next). 0/không đặt = không giới hạn.
        self.max_pages = config.get("max_pages", 0) or 0
        # Một URL có thể được retry hoặc fallback Playwright. Chỉ tính một lần
        # khi URL đó thực sự thất bại để dashboard phản ánh đúng số trang lỗi.
        self._failed_urls = set()

    def _record_page_failure(self, url):
        """Tăng custom stat đúng một lần cho mỗi URL lỗi."""
        if url in self._failed_urls:
            return
        self._failed_urls.add(url)
        self.crawler.stats.inc_value("pages_failed")


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                errback=self.handle_request_error,
                meta={"is_fallback": False, "page_count": 1},
            )

    def handle_request_error(self, failure):
        """Ghi nhận lỗi tải từng URL sau khi Scrapy đã retry, không dừng spider."""
        request = getattr(failure, "request", None)
        url = getattr(request, "url", "<unknown URL>")
        error_type = getattr(getattr(failure, "type", None), "__name__", type(failure).__name__)
        reason = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
        self.logger.error(
            "Không thể tải trang | URL: %s | Lỗi: %s | Lý do: %s",
            url,
            error_type,
            reason,
        )
        self._record_page_failure(url)

    def _extract_text(self, response):
        """Lấy text thô từ content_selector để đánh giá độ dài nội dung.

        Loại bỏ text node nằm trong <script>/<style> để tránh lẫn code JS/CSS
        vào content (vd: document.write(...), oscar.init()...).
        """
        content_nodes = response.css(self.content_selector)
        text_parts = content_nodes.xpath(
            ".//text()[not(ancestor::script) and not(ancestor::style)]"
        ).getall()
        return " ".join(part.strip() for part in text_parts if part.strip())

    def _is_content_insufficient(self, response):
        """Phát hiện trang gần như rỗng/thiếu nội dung mong đợi (dấu hiệu cần JS render).

        Điều kiện coi là "thiếu nội dung":
        - Text trong content_selector quá ngắn (< MIN_CONTENT_LENGTH ký tự), hoặc
        - Không tìm thấy phần tử nào khớp content_selector.
        """
        content_nodes = response.css(self.content_selector)
        if not content_nodes:
            return True
        text = self._extract_text(response)
        return len(text) < MIN_CONTENT_LENGTH

    def _extract_product_item(self, node, response, now):
        """Tạo 1 CrawlerItem từ 1 phần tử khớp content_selector (vd: .product_pod,
        .thumbnail).

        Thử nhiều selector fallback để hỗ trợ cả cấu trúc books.toscrape.com
        (h3 > a[title], .price_color, .availability) và webscraper.io
        (a.title[title], h4.price [itemprop=price], schema.org microdata).
        Lấy title từ attribute title của thẻ a (thay vì text bị cắt "...").
        """
        title = (
            node.css("h3 a::attr(title)").get()
            or node.css("a.title::attr(title)").get()
            or node.css("[itemprop='name']::attr(title)").get()
            or node.css("h3 a::text").get()
            or node.css("a.title::text").get()
            or node.css("[itemprop='name']::text").get()
        )

        price = node.css(".price_color::text").get()
        if not price:
            price_parts = node.css(".price ::text, [itemprop='price']::text").getall()
            price = " ".join(part.strip() for part in price_parts if part.strip()) or None

        availability = " ".join(
            part.strip()
            for part in node.css(".availability::text").getall()
            if part.strip()
        )

        detail_href = (
            node.css("h3 a::attr(href)").get()
            or node.css("a.title::attr(href)").get()
            or node.css("[itemprop='name']::attr(href)").get()
        )
        detail_url = response.urljoin(detail_href) if detail_href else response.url

        item = CrawlerItem()
        item["url"] = detail_url
        item["title"] = (title or "").strip()
        item["price"] = (price or "").strip()
        item["availability"] = availability
        item["crawled_at"] = now
        return item


    def _next_page_url(self, response):
        """Tìm link phân trang <li class="next"><a href="...">, trả về None nếu hết trang."""
        return response.css("li.next a::attr(href)").get()

    def parse(self, response):
        is_fallback = response.meta.get("is_fallback", False)
        page_count = response.meta.get("page_count", 1)

        # Nếu đây là response tĩnh (chưa dùng Playwright) và nội dung thiếu,
        # phát lại request qua Playwright để render JS rồi parse lại.
        try:
            if not is_fallback and self._is_content_insufficient(response):
                self.logger.info(
                    "Nội dung tĩnh quá ít (%s), fallback sang Playwright: %s",
                    len(self._extract_text(response)),
                    response.url,
                )
                yield scrapy.Request(
                    response.url,
                    callback=self.parse,
                    errback=self.handle_request_error,
                    dont_filter=True,
                    meta={
                        "is_fallback": True,
                        "playwright": True,
                        "playwright_include_page": False,
                        "page_count": page_count,
                    },
                )
                return

            # content_selector (vd: ".product_pod") có thể khớp nhiều phần tử
            # trên 1 trang -> yield 1 Item riêng cho MỖI phần tử.
            content_nodes = response.css(self.content_selector)
            if not content_nodes:
                raise ValueError(f"Selector không khớp phần tử nào: {self.content_selector!r}")

            if is_fallback:
                self.logger.info("Đã render bằng Playwright thành công: %s", response.url)

            now = datetime.now(timezone.utc).isoformat()
            for node in content_nodes:
                try:
                    yield self._extract_product_item(node, response, now)
                except Exception as exc:  # noqa: BLE001 - không bỏ cả trang vì 1 item lỗi
                    self.logger.exception(
                        "Không thể trích xuất item | URL: %s | Lỗi: %s: %s",
                        response.url,
                        type(exc).__name__,
                        exc,
                    )
        except Exception as exc:  # noqa: BLE001 - log lỗi response và vẫn thử trang kế tiếp
            self.logger.exception(
                "Không thể trích xuất dữ liệu từ trang | URL: %s | Lỗi: %s: %s",
                response.url,
                type(exc).__name__,
                exc,
            )
            self._record_page_failure(response.url)

        # Tách riêng việc follow phân trang: trang hiện tại lỗi extract vẫn không
        # làm dừng các trang phía sau nếu link phân trang vẫn đọc được.
        try:
            next_href = self._next_page_url(response)
            if next_href and (self.max_pages <= 0 or page_count < self.max_pages):
                next_url = response.urljoin(next_href)
                yield scrapy.Request(
                    next_url,
                    callback=self.parse,
                    errback=self.handle_request_error,
                    meta={"is_fallback": False, "page_count": page_count + 1},
                )
        except Exception as exc:  # noqa: BLE001 - lỗi pagination không crash spider
            self.logger.exception(
                "Không thể đọc phân trang | URL: %s | Lỗi: %s: %s",
                response.url,
                type(exc).__name__,
                exc,
            )
