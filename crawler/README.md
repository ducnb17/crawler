# Crawler

Scrapy spider tổng quát (`GenericSpider`), tự fallback sang Playwright khi
trang cần render JavaScript. Toàn bộ cấu hình nằm trong `config.yaml`,
không cần sửa code khi đổi mục tiêu crawl.

## Cấu hình (`config.yaml`)

```yaml
start_urls:
  - "https://quotes.toscrape.com/js/"

allowed_domains:
  - "quotes.toscrape.com"

title_selector: "title::text"
content_selector: ".quote"

delay: 1          # giây, độ trễ giữa các request (DOWNLOAD_DELAY)
user_agent: "crawler-bot/1.0 (+https://github.com/your-org/crawler; contact: your-email@example.com)"
max_pages: 50      # số item tối đa crawl trong 1 lần chạy, 0 = không giới hạn
```

Để crawl trang khác, chỉ cần sửa các trường trên:

- `start_urls`: danh sách URL bắt đầu crawl.
- `allowed_domains`: domain được phép crawl (chống crawl lan sang site khác).
- `title_selector` / `content_selector`: CSS selector để lấy tiêu đề/nội dung.
- `delay`: tăng nếu site nhạy với tốc độ request, giảm nếu cần crawl nhanh hơn.
- `user_agent`: nên để lại thông tin liên hệ thật để chủ site có thể phản hồi.
- `max_pages`: giới hạn số item để tránh crawl quá nhiều ngoài ý muốn.

Biến môi trường `CRAWLER_USER_AGENT`, `CRAWLER_DOWNLOAD_DELAY`,
`CRAWLER_MAX_PAGES` (và các biến `CRAWLER_*` khác trong `settings.py`) sẽ
override giá trị trong `config.yaml` nếu được set — hữu ích khi deploy/CI.

## Cài đặt

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Chạy crawl

Chạy từ thư mục gốc project (chứa `scrapy.cfg`):

```bash
python -m scrapy crawl generic_spider
```

Kết quả được lưu vào:

- `crawler/output.jsonl`: mỗi dòng là 1 item JSON, ghi tiếp qua các lần chạy.
- `crawler/crawled_data.db`: SQLite, bảng `items`, dùng để dedup theo `url`
  (item có URL đã crawl trước đó sẽ bị bỏ qua, không lưu trùng).

## Fallback Playwright

Nếu HTML tĩnh trả về thiếu nội dung (không tìm thấy `content_selector`, hoặc
text quá ngắn), spider tự động gửi lại request qua `scrapy-playwright` để
render JavaScript rồi extract lại. Việc này diễn ra tự động, không cần cấu
hình thêm.

## Error handling & log

- Request lỗi tạm thời (500/502/503/504/522/524/408/429 hoặc timeout) sẽ tự
  retry tối đa `RETRY_TIMES` lần (mặc định 3), override qua `CRAWLER_RETRY_TIMES`.
- `DOWNLOAD_TIMEOUT` (mặc định 30s) chỉnh qua `CRAWLER_DOWNLOAD_TIMEOUT`.
- Log ghi ra file `crawler/crawler.log` (không chỉ console), đường dẫn/level
  chỉnh qua `CRAWLER_LOG_FILE` / `CRAWLER_LOG_LEVEL`.
- Nếu thấy site chặn/trả 429 liên tục: tăng `delay` trong `config.yaml` hoặc
  giảm `CONCURRENT_REQUESTS_PER_DOMAIN` trong `settings.py`.


