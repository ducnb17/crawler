"""Item pipeline: lưu Item qua crawler.core.storage.ItemStore (dùng chung
với nhánh Requests+BS4 trong core/fetcher.py).

Việc lưu JSONL/SQLite + dedup theo URL nay được xử lý tập trung trong
core/storage.py, tránh 2 nơi định nghĩa schema/logic dedup khác nhau.
"""

import json
import os

from crawler.core.storage import ItemStore

OUTPUT_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.json")


class CrawlerPipeline:
    """Ghi item vào JSONL + SQLite (qua ItemStore), dedup theo URL (không lưu trùng)."""

    def open_spider(self, spider):
        self.store = ItemStore().open()

    def close_spider(self, spider):
        self.store.close()

    def process_item(self, item, spider):
        from scrapy.exceptions import DropItem

        row = dict(item)
        url = row.get("url")
        if not url:
            raise DropItem("Item thiếu url, không thể dedup/lưu")

        if not self.store.save(row):
            raise DropItem(f"Item trùng URL đã crawl trước đó: {url}")

        return item


class DuplicatesPipeline:
    """Chặn item trùng dựa trên URL/ID bằng set() in-memory.

    Đặt priority thấp hơn (chạy trước) CrawlerPipeline/JsonWriterPipeline
    trong settings.py để loại item trùng ngay từ đầu chain, tránh các
    pipeline sau phải xử lý item dư thừa.
    """

    def open_spider(self, spider):
        self.seen_keys = set()

    def process_item(self, item, spider):
        from scrapy.exceptions import DropItem

        row = dict(item)
        # Ưu tiên "id" nếu item có, không thì fallback dùng "url".
        key = row.get("id") or row.get("url")
        if not key:
            raise DropItem("Item thiếu url/id, không thể dedup")

        if key in self.seen_keys:
            raise DropItem(f"Item trùng (key={key})")

        self.seen_keys.add(key)
        return item


class JsonWriterPipeline:
    """Thu thập toàn bộ item trong quá trình crawl, ghi ra output.json
    (JSON array, UTF-8) 1 lần khi spider đóng.
    """

    def open_spider(self, spider):
        self.items = []

    def process_item(self, item, spider):
        self.items.append(dict(item))
        return item

    def close_spider(self, spider):
        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
