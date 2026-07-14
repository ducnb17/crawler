# CLAUDE.md

## Build & Run Commands
- Activate venv: `source venv_wsl/bin/activate`
- Run single scraper: `python core/fetcher.py`
- Run Scrapy spider: `scrapy crawl <spider_name>`
- Install deps: `pip install -r requirements.txt`

## Code Style
- Snake_case cho hàm/biến, PascalCase cho Class.
- Mọi hàm HTTP Request đều phải có try-catch và log lỗi rõ ràng.

## Workflow & Safety
- Trả lời ngắn gọn, đi thẳng vào vấn đề.
- Luôn báo cho user biết file nào sắp sửa đổi trước khi ghi file.