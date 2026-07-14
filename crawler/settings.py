# Scrapy settings cho project "crawler".
# Tài liệu tham khảo: https://docs.scrapy.org/en/latest/topics/settings.html
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
import os

import yaml

BOT_NAME = "crawler"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# --- Đọc config.yaml (user_agent, delay, max_pages...) để tránh hardcode ---
# Biến môi trường (nếu có) vẫn được ưu tiên cao nhất, dùng cho override khi
# deploy/CI mà không cần sửa file config.
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def _load_yaml_config():
    if not os.path.exists(_CONFIG_PATH):
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_config = _load_yaml_config()

# --- User-Agent: rotate ngẫu nhiên qua RandomUserAgentMiddleware (middlewares.py) ---

# USER_AGENT ở đây chỉ là giá trị mặc định/fallback (dùng cho request nào
# middleware chưa gán được UA), giá trị thật sự dùng cho từng request được
# RandomUserAgentMiddleware set lại (xem DOWNLOADER_MIDDLEWARES bên dưới).
USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    _config.get(
        "user_agent",
        "crawler-bot/1.0 (+https://github.com/your-org/crawler; contact: your-email@example.com)",
    ),
)

# --- Anti-bot: rotate UA ngẫu nhiên + tự bypass Cloudflare 5s challenge ---
# Tắt UserAgentMiddleware mặc định (dùng USER_AGENT cố định) để
# RandomUserAgentMiddleware toàn quyền gán UA cho mỗi request.
# CloudscraperMiddleware đặt priority cao (900, gần cuối chain response) để
# nhận response đã qua RetryMiddleware/HttpErrorMiddleware xử lý status code.
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "crawler.middlewares.RandomUserAgentMiddleware": 400,
    "crawler.middlewares.CloudscraperMiddleware": 900,
}

# --- Tuân thủ robots.txt (có thể bật lại qua env nếu cần crawl lịch sự hơn) ---
# Mặc định False (anti-ban baseline) vì nhiều site chặn crawl qua robots.txt
# dù nội dung công khai; đổi CRAWLER_ROBOTSTXT_OBEY=True nếu cần tuân thủ.
ROBOTSTXT_OBEY = os.getenv("CRAWLER_ROBOTSTXT_OBEY", "False") == "True"


# --- Giới hạn độ sâu: KHÔNG đặt cứng ở đây vì generic_spider.py đã tự quản lý
# số trang phân trang qua config.yaml (max_pages) bằng page_count trong meta.
# Đặt DEPTH_LIMIT thấp (vd: 3) sẽ khiến DepthMiddleware chặn request phân trang
# sớm hơn max_pages mong muốn, làm crawl bị cắt ngang. 0 = không giới hạn.
DEPTH_LIMIT = int(os.getenv("CRAWLER_DEPTH_LIMIT", "0"))

# --- Tốc độ crawl hợp lý, tránh gây tải cho server đích (anti-ban baseline) ---
# Thứ tự ưu tiên: biến môi trường > config.yaml (delay) > default (2s).
DOWNLOAD_DELAY = float(os.getenv("CRAWLER_DOWNLOAD_DELAY", str(_config.get("delay", 2))))
# Random hoá delay trong khoảng [0.5*DOWNLOAD_DELAY, 1.5*DOWNLOAD_DELAY] để
# tránh pattern request đều đặn (dễ bị site phát hiện là bot).
RANDOMIZE_DOWNLOAD_DELAY = True
# Giới hạn số request đồng thời thấp để giảm nguy cơ bị chặn/ban IP.
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# --- Giới hạn số trang tối đa crawl (config.yaml: max_pages) đã được xử lý
# trực tiếp trong generic_spider.py (so sánh page_count với self.max_pages
# trước khi follow link phân trang). KHÔNG dùng CLOSESPIDER_ITEMCOUNT ở đây
# vì max_pages là số TRANG, không phải số ITEM (mỗi trang có nhiều item).



# --- AutoThrottle: tự điều chỉnh tốc độ theo tải của server đích ---
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = float(os.getenv("CRAWLER_AUTOTHROTTLE_START_DELAY", "1"))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv("CRAWLER_AUTOTHROTTLE_MAX_DELAY", "10"))
# Số request đồng thời trung bình mong muốn cho mỗi domain.
AUTOTHROTTLE_TARGET_CONCURRENCY = float(
    os.getenv("CRAWLER_AUTOTHROTTLE_TARGET_CONCURRENCY", "1.0")
)
# Bật để log throttle stats cho mỗi response nhận được (hữu ích khi debug).
AUTOTHROTTLE_DEBUG = os.getenv("CRAWLER_AUTOTHROTTLE_DEBUG", "False") == "True"

# --- Cache HTTP để tránh crawl lại dữ liệu không đổi (tuỳ chọn, mặc định tắt) ---
HTTPCACHE_ENABLED = os.getenv("CRAWLER_HTTPCACHE_ENABLED", "False") == "True"
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = "httpcache"

# --- Retry khi timeout/lỗi tạm thời (RetryMiddleware đã bật sẵn theo default) ---
# Số lần thử lại tối đa cho 1 request trước khi bỏ qua.
RETRY_TIMES = int(os.getenv("CRAWLER_RETRY_TIMES", "3"))
# Mã lỗi HTTP sẽ được retry (thêm 429 - too many requests, dấu hiệu bị chặn).
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]
# Timeout cho mỗi request (giây) trước khi coi là lỗi và trigger retry.
DOWNLOAD_TIMEOUT = int(os.getenv("CRAWLER_DOWNLOAD_TIMEOUT", "30"))

# --- Log in thẳng ra console (terminal), KHÔNG ghi ra file ---
# Bỏ LOG_FILE để Scrapy in log qua stdout/stderr, dễ theo dõi trực tiếp
# khi chạy tay. Nếu cần lưu lịch sử log, dùng redirect ở lệnh chạy
# (vd: `scrapy crawl generic_spider 2>&1 | tee crawl.log`) chứ không ép
# cứng trong settings.
LOG_LEVEL = os.getenv("CRAWLER_LOG_LEVEL", "INFO")


# --- Item pipelines, thứ tự ưu tiên theo số (số nhỏ chạy trước) ---
# 1. DuplicatesPipeline: chặn item trùng (set() in-memory) sớm nhất, để các
#    pipeline sau không phải xử lý item dư thừa.
# 2. CrawlerPipeline: dedup theo URL (SQLite) + lưu SQLite/output.jsonl,
#    dùng chung schema với nhánh Requests+BS4 (core/fetcher.py).
# 3. JsonWriterPipeline: gom toàn bộ item còn lại, ghi 1 lần ra output.json
#    (JSON array, UTF-8) khi spider đóng.
ITEM_PIPELINES = {
    "crawler.pipelines.DuplicatesPipeline": 300,
    "crawler.pipelines.CrawlerPipeline": 400,
    "crawler.pipelines.JsonWriterPipeline": 500,
}

# --- Bắt buộc dùng asyncio reactor để scrapy-playwright hoạt động ---
# Reactor được chọn lúc khởi động process nên phải khai báo ở đây (global settings),
# đặt trong custom_settings của spider sẽ không có tác dụng.
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"



