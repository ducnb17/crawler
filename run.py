"""CLI entry point để chạy crawler theo 2 cách:

1. fetch : Requests/Cloudscraper + BeautifulSoup4 (crawler/core/fetcher.py).
2. spider: Scrapy Spider chạy qua CrawlerProcess (không cần lệnh `scrapy crawl`).

Usage:
    python run.py fetch --mode anti_cf --url https://example.com
    python run.py spider --name generic_spider
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("run")


def run_fetch(args) -> int:
    """Fetch 1 hoặc nhiều URL qua SmartFetcher (Requests/Cloudscraper) + BS4,
    lưu kết quả qua ItemStore (SQLite + JSONL), bắt lỗi rõ ràng cho mỗi URL."""
    from datetime import datetime, timezone

    import requests

    from crawler.core.fetcher import SmartFetcher, parse_html
    from crawler.core.storage import ItemStore
    from crawler.spiders.spiders import load_config

    config = load_config()
    urls = [args.url] if args.url else config.get("start_urls", [])
    if not urls:
        logger.error(
            "Không có URL để fetch. Truyền --url hoặc khai báo start_urls trong config.yaml"
        )
        return 1

    fetcher = SmartFetcher(mode=args.mode)
    exit_code = 0

    with ItemStore() as store:
        for url in urls:
            try:
                response = fetcher.get(url)
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                logger.error("Lỗi kết nối/HTTP khi fetch %s: %s", url, exc)
                exit_code = 1
                continue

            try:
                data = parse_html(response.text)
                row = {
                    "url": url,
                    "title": data.get("title", ""),
                    "content": data.get("meta_description", ""),
                    "price": "",
                    "availability": "",
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                }
                if store.save(row):
                    logger.info("Đã lưu: %s (title=%s)", url, row["title"])
                else:
                    logger.info("Bỏ qua (trùng URL hoặc thiếu url): %s", url)
            except Exception as exc:  # noqa: BLE001 - bắt mọi lỗi parse/lưu, log rõ, không crash toàn batch
                logger.error("Lỗi khi parse/lưu dữ liệu từ %s: %s", url, exc)
                exit_code = 1

    return exit_code


def run_spider(args) -> int:
    """Chạy 1 Scrapy Spider trực tiếp qua CrawlerProcess, không cần lệnh `scrapy crawl`."""
    try:
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings
    except ImportError as exc:
        logger.error("Thiếu dependency Scrapy: %s. Chạy `pip install -r requirements.txt`.", exc)
        return 1

    try:
        settings = get_project_settings()
        process = CrawlerProcess(settings)
        process.crawl(args.name)
        process.start()  # block tới khi crawl xong (hoặc lỗi)
    except KeyError as exc:
        logger.error("Không tìm thấy spider tên '%s': %s", args.name, exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - bắt mọi lỗi runtime của Scrapy, log rõ ràng
        logger.error("Lỗi khi chạy spider '%s': %s", args.name, exc)
        return 1

    logger.info("Spider '%s' đã chạy xong.", args.name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chạy crawler: fetch đơn (Requests/Cloudscraper+BS4) hoặc Scrapy Spider."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch qua Cloudscraper/Requests + BeautifulSoup4 (core/fetcher.py)."
    )
    fetch_parser.add_argument(
        "--mode",
        choices=["standard", "anti_cf"],
        default="standard",
        help="'standard' (requests thường) hoặc 'anti_cf' (cloudscraper, bypass Cloudflare).",
    )
    fetch_parser.add_argument(
        "--url",
        default=None,
        help="URL cần fetch. Nếu bỏ qua, dùng start_urls trong config.yaml.",
    )

    spider_parser = subparsers.add_parser(
        "spider", help="Chạy Scrapy Spider qua CrawlerProcess (thay cho `scrapy crawl`)."
    )
    spider_parser.add_argument(
        "--name",
        default="generic_spider",
        help="Tên spider (mặc định: generic_spider). Xem crawler/spiders/.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "fetch":
            return run_fetch(args)
        if args.command == "spider":
            return run_spider(args)
    except KeyboardInterrupt:
        logger.warning("Đã dừng theo yêu cầu người dùng (Ctrl+C).")
        return 130
    except Exception as exc:  # noqa: BLE001 - safety net cuối cùng, không để crash im lặng
        logger.error("Lỗi không mong đợi: %s", exc, exc_info=True)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

