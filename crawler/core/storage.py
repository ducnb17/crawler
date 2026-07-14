"""Storage layer dùng chung cho cả 2 nhánh crawl (Scrapy pipeline & core/fetcher.py).

Chuẩn hoá 1 nguồn dữ liệu duy nhất:
- SQLite (crawled_data.db): bảng `items`, url là PRIMARY KEY -> dedup.
- JSONL (output.jsonl): append-only, giữ lịch sử tất cả item đã lưu.
- CSV export theo yêu cầu (export_csv()), không tự động ghi mỗi lần crawl.
"""

import csv
import json
import os
import sqlite3
import threading

OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONL_PATH = os.path.join(OUTPUT_DIR, "output.jsonl")
SQLITE_PATH = os.path.join(OUTPUT_DIR, "crawled_data.db")

ITEM_COLUMNS = ("url", "title", "content", "price", "availability", "crawled_at")

# Lock bảo vệ ghi JSONL/SQLite khi nhiều thread cùng gọi (vd: fetcher.py
# dùng ThreadPoolExecutor để fetch song song nhiều URL).
_write_lock = threading.Lock()


class ItemStore:
    """Lưu item vào SQLite + JSONL, dedup theo URL. Có thể dùng làm context manager."""

    def __init__(self, sqlite_path: str = SQLITE_PATH, jsonl_path: str = JSONL_PATH):
        self.sqlite_path = sqlite_path
        self.jsonl_path = jsonl_path
        self.conn = None
        self.jsonl_file = None
        self.seen_urls = set()

    def open(self):
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                url TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                price TEXT,
                availability TEXT,
                crawled_at TEXT
            )
            """
        )
        existing_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(items)")}
        for col in ("price", "availability"):
            if col not in existing_cols:
                self.conn.execute(f"ALTER TABLE items ADD COLUMN {col} TEXT")
        self.conn.commit()

        cursor = self.conn.execute("SELECT url FROM items")
        self.seen_urls = {row[0] for row in cursor.fetchall()}

        self.jsonl_file = open(self.jsonl_path, "a", encoding="utf-8")
        return self

    def close(self):
        if self.jsonl_file:
            self.jsonl_file.close()
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def save(self, row: dict) -> bool:
        """Lưu 1 item (dict). Trả về True nếu lưu thành công, False nếu bị dedup/thiếu url."""
        url = row.get("url")
        if not url:
            return False

        with _write_lock:
            if url in self.seen_urls:
                return False
            self.seen_urls.add(url)

            clean_row = {col: row.get(col, "") for col in ITEM_COLUMNS}
            self.jsonl_file.write(json.dumps(clean_row, ensure_ascii=False) + "\n")
            self.jsonl_file.flush()

            self.conn.execute(
                "INSERT INTO items (url, title, content, price, availability, crawled_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                tuple(clean_row[col] for col in ITEM_COLUMNS),
            )
            self.conn.commit()
        return True


def export_csv(csv_path: str = None, sqlite_path: str = SQLITE_PATH) -> str:
    """Xuất toàn bộ bảng `items` trong SQLite ra file CSV. Trả về đường dẫn file đã ghi."""
    if csv_path is None:
        csv_path = os.path.join(OUTPUT_DIR, "output.csv")

    conn = sqlite3.connect(sqlite_path)
    try:
        cursor = conn.execute(
            f"SELECT {', '.join(ITEM_COLUMNS)} FROM items ORDER BY crawled_at DESC"
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(ITEM_COLUMNS)
        writer.writerows(rows)

    return csv_path
