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


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={"is_fallback": False, "page_count": 1},
            )

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
        if not is_fallback and self._is_content_insufficient(response):
            self.logger.info(
                "Nội dung tĩnh quá ít (%s), fallback sang Playwright: %s",
                len(self._extract_text(response)),
                response.url,
            )
            yield scrapy.Request(
                response.url,
                callback=self.parse,
                dont_filter=True,
                meta={
                    "is_fallback": True,
                    "playwright": True,
                    "playwright_include_page": False,
                    "page_count": page_count,
                },
            )
            return

        if is_fallback:
            self.logger.info("Đã render bằng Playwright thành công: %s", response.url)

        now = datetime.now(timezone.utc).isoformat()

        # content_selector (vd: ".product_pod") có thể khớp nhiều phần tử trên
        # 1 trang (nhiều sách) -> yield 1 Item riêng cho MỖI phần tử, không gộp
        # chung thành 1 blob text.
        content_nodes = response.css(self.content_selector)
        for node in content_nodes:
            yield self._extract_product_item(node, response, now)

        # Theo link phân trang <li class="next"><a href="..."> để crawl hết các
        # trang danh sách, giới hạn bởi max_pages trong config.yaml (0 = không giới hạn).
        next_href = self._next_page_url(response)
        if next_href and (self.max_pages <= 0 or page_count < self.max_pages):
            next_url = response.urljoin(next_href)
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={"is_fallback": False, "page_count": page_count + 1},
            )
