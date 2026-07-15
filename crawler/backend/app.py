import asyncio
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

app = FastAPI(title="Crawler Dashboard API")

# Cho phép frontend (mở từ file:// hoặc từ một origin khác) gọi API này.
# Vì đây là dashboard nội bộ chạy trên máy dev, allow_origins="*" là chấp nhận được.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Thư mục gốc của project crawler (nơi có spiders/, settings.py, ...).
# app.py nằm ở crawler/backend/app.py nên gốc project là parent.parent.
CRAWLER_ROOT = Path(__file__).resolve().parent.parent

# Thư mục chứa frontend (dashboard tĩnh: index.html).
FRONTEND_DIR = CRAWLER_ROOT / "frontend"

# Đường dẫn SQLite phải khớp với SQLITE_PATH trong pipelines.py
# (bảng `items`, cột: url, title, content, price, availability, crawled_at).
SQLITE_PATH = CRAWLER_ROOT / "crawled_data.db"

# Đường dẫn config.yaml phải khớp với CONFIG_PATH trong settings.py /
# spiders/generic_spider.py.
CONFIG_PATH = CRAWLER_ROOT / "config.yaml"



@app.get("/", include_in_schema=False)
def serve_frontend():
    """Phục vụ dashboard tĩnh tại '/' để chạy chung 1 server với API."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail=f"Frontend not found at {index_path}")
    return FileResponse(index_path)



# --- Trạng thái crawl lưu in-memory (mất khi restart server, đủ dùng cho dashboard) ---
_crawl_state: dict = {
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "returncode": None,
    "error": None,
    "pages_crawled": None,
    "pages_failed": None,
}
# Lock để tránh 2 request POST /crawl cùng lúc khởi chạy 2 subprocess song song.
_crawl_lock = asyncio.Lock()
_crawl_task: Optional[asyncio.Task] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_scrapy_stats(output_text: str) -> tuple[int, int]:
    """Parse Scrapy stats từ output text để lấy pages_crawled và pages_failed.
    
    Scrapy in stats block ở cuối output với format:
    [scrapy.statscollectors] INFO: Dumping Scrapy stats:
    {'response_received_count': 10,
     'downloader/exception_count': 2,
     ...}
    
    Returns:
        tuple[pages_crawled, pages_failed]
    """
    import re
    
    pages_crawled = 0
    pages_failed = 0
    
    # Extract response_received_count (số trang crawl thành công)
    match = re.search(r"'response_received_count':\s*(\d+)", output_text)
    if match:
        pages_crawled = int(match.group(1))
    
    # `pages_failed` là custom stat do GenericSpider ghi một lần cho mỗi URL
    # không thể trích xuất. Không dùng downloader/exception_count vì chỉ số đó
    # bao gồm từng lần retry, làm số trang lỗi bị đếm lặp.
    match = re.search(r"'pages_failed':\s*(\d+)", output_text)
    if match:
        pages_failed += int(match.group(1))

    # retry/max_reached tăng một lần cho mỗi request đã dùng hết retry, trái
    # với downloader/exception_count tăng theo từng attempt.
    match = re.search(r"'retry/max_reached':\s*(\d+)", output_text)
    if match:
        pages_failed += int(match.group(1))

    # HTTP status bị HttpErrorMiddleware bỏ qua không đi qua parse(), nên
    # không được GenericSpider ghi custom stat.
    match = re.search(r"'httperror/response_ignored_count':\s*(\d+)", output_text)
    if match:
        pages_failed += int(match.group(1))
    
    return pages_crawled, pages_failed


async def _run_crawl_process(
    start_url: Optional[str] = None,
    allowed_domain: Optional[str] = None,
    css_selector: Optional[str] = None,
) -> None:
    """Chạy `scrapy crawl generic_spider` trong CRAWLER_ROOT, không chặn event loop.

    Nếu start_url/allowed_domain/css_selector được truyền vào (từ Frontend),
    chúng được forward qua `-a` cho spider (xem GenericSpider.__init__ trong
    spiders/spiders.py), có độ ưu tiên cao hơn config.yaml. Nếu không truyền
    (None/rỗng), spider sẽ tự fallback đọc config.yaml như cũ.
    """
    log_path = CRAWLER_ROOT / "crawl_log.txt"

    cmd = [sys.executable, "-m", "scrapy", "crawl", "generic_spider"]
    if start_url:
        cmd += ["-a", f"start_url={start_url}"]
    if allowed_domain:
        cmd += ["-a", f"allowed_domain={allowed_domain}"]
    if css_selector:
        cmd += ["-a", f"css_selector={css_selector}"]

    # Log rõ ràng ra terminal (stdout của tiến trình uvicorn) để dev theo dõi
    # trực tiếp, đồng thời vẫn ghi lại đầy đủ vào crawl_log.txt.
    print("=" * 70, flush=True)
    print(f"[CRAWL] Bắt đầu lúc {_now_iso()}", flush=True)
    print(f"[CRAWL] Lệnh chạy: {' '.join(cmd)}", flush=True)
    print(f"[CRAWL] cwd={CRAWLER_ROOT}", flush=True)
    print("=" * 70, flush=True)

    try:
        output_buffer = []  # Buffer to collect all output for stats parsing
        
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n----- Crawl started at {_now_iso()} -----\n")
            log_file.write(f"Command: {' '.join(cmd)}\n")
            log_file.flush()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(CRAWLER_ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Đọc từng dòng output của scrapy, vừa in ra terminal vừa ghi log file,
            # để dev thấy tiến trình crawl chạy real-time.
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                print(f"[scrapy] {decoded}", end="", flush=True)
                log_file.write(decoded)
                log_file.flush()
                output_buffer.append(decoded)

            returncode = await process.wait()

        # Parse stats từ output buffer sau khi subprocess kết thúc
        full_output = "".join(output_buffer)
        pages_crawled, pages_failed = _parse_scrapy_stats(full_output)
        
        _crawl_state["returncode"] = returncode
        _crawl_state["finished_at"] = _now_iso()
        _crawl_state["pages_crawled"] = pages_crawled
        _crawl_state["pages_failed"] = pages_failed
        
        if returncode == 0:
            _crawl_state["status"] = "done"
            _crawl_state["error"] = None
            print(f"[CRAWL] Hoàn tất thành công lúc {_now_iso()}", flush=True)
            print(f"[CRAWL] Stats: {pages_crawled} pages crawled, {pages_failed} pages failed", flush=True)
        else:
            _crawl_state["status"] = "error"
            _crawl_state["error"] = f"scrapy exited with code {returncode}"
            print(f"[CRAWL] Lỗi: scrapy exited with code {returncode}", flush=True)
    except Exception as exc:  # noqa: BLE001 - muốn bắt mọi lỗi để phản ánh vào status
        _crawl_state["status"] = "error"
        _crawl_state["error"] = str(exc)
        _crawl_state["finished_at"] = _now_iso()
        print(f"[CRAWL] Exception: {exc}", flush=True)


@app.get("/health")
def health():
    return {"status": "ok"}


class StartCrawlRequest(BaseModel):
    """Body (tuỳ chọn) cho POST /crawl, forward trực tiếp tới spider qua `-a`.

    Nếu không gửi (hoặc field rỗng), spider sẽ tự fallback đọc config.yaml
    (xem GenericSpider.__init__ trong spiders/spiders.py).
    """

    start_url: Optional[str] = None
    allowed_domain: Optional[str] = None
    css_selector: Optional[str] = None


@app.post("/crawl")
async def start_crawl(payload: StartCrawlRequest = StartCrawlRequest()):
    global _crawl_task

    async with _crawl_lock:
        if _crawl_state["status"] == "running":
            raise HTTPException(status_code=409, detail="Crawl is already running")

        _crawl_state["status"] = "running"
        _crawl_state["started_at"] = _now_iso()
        _crawl_state["finished_at"] = None
        _crawl_state["returncode"] = None
        _crawl_state["error"] = None
        _crawl_state["pages_crawled"] = None
        _crawl_state["pages_failed"] = None

        print(
            f"[CRAWL] Nhận yêu cầu Start Crawl: start_url={payload.start_url!r}, "
            f"allowed_domain={payload.allowed_domain!r}, css_selector={payload.css_selector!r}",
            flush=True,
        )

        # Chạy subprocess ở background, không await ở đây để không chặn response.
        _crawl_task = asyncio.create_task(
            _run_crawl_process(
                start_url=payload.start_url,
                allowed_domain=payload.allowed_domain,
                css_selector=payload.css_selector,
            )
        )

    return {"status": _crawl_state["status"], "started_at": _crawl_state["started_at"]}



@app.get("/crawl/status")
def crawl_status():
    return {
        "status": _crawl_state["status"],
        "started_at": _crawl_state["started_at"],
        "finished_at": _crawl_state["finished_at"],
        "returncode": _crawl_state["returncode"],
        "error": _crawl_state["error"],
        "pages_crawled": _crawl_state["pages_crawled"],
        "pages_failed": _crawl_state["pages_failed"],
    }


def _get_db_connection() -> sqlite3.Connection:
    """Mở kết nối tới crawled_data.db (được tạo bởi pipelines.py)."""
    if not SQLITE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Database not found at {SQLITE_PATH}. Hãy chạy crawl trước.",
        )
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _result_columns(items: list[dict]) -> list[str]:
    """Lấy union các key theo thứ tự xuất hiện, với URL/thời gian ở hai đầu."""
    columns: list[str] = []
    seen: set[str] = set()
    for item in items:
        for key in item:
            if key not in seen:
                columns.append(key)
                seen.add(key)

    # Chỉ đưa các cột thực sự có trong dữ liệu vào response.
    if "url" in seen:
        columns.remove("url")
        columns.insert(0, "url")
    if "crawled_at" in seen:
        columns.remove("crawled_at")
        columns.append("crawled_at")

    return columns


@app.get("/results")
def get_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, description="Tìm theo title"),
):
    conn = _get_db_connection()
    try:
        where_clause = ""
        params: list = []
        if search:
            where_clause = "WHERE title LIKE ?"
            params.append(f"%{search}%")

        total_items = conn.execute(
            f"SELECT COUNT(*) FROM items {where_clause}", params
        ).fetchone()[0]
        total_pages = math.ceil(total_items / page_size) if total_items else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM items {where_clause} "
            f"ORDER BY crawled_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

        items = [dict(row) for row in rows]

        return {
            "items": items,
            "columns": _result_columns(items),
            "total_items": total_items,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


@app.get("/stats")
def get_stats():
    conn = _get_db_connection()
    try:
        total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        last_crawled_at = conn.execute(
            "SELECT MAX(crawled_at) FROM items"
        ).fetchone()[0]

        return {
            "total_items": total_items,
            "last_crawled_at": last_crawled_at,
        }
    finally:
        conn.close()


# --- Đọc/ghi config.yaml (start_urls, allowed_domains, selectors, max_pages) ---

class CrawlerConfig(BaseModel):
    """Schema cho phần config.yaml mà dashboard được phép chỉnh sửa.

    Các field khác trong config.yaml (delay, user_agent) không được quản lý
    qua API này nên sẽ được giữ nguyên khi ghi đè file.
    """

    start_urls: List[str]
    allowed_domains: List[str]
    content_selector: str
    title_selector: str
    max_pages: int = 0

    @field_validator("start_urls")
    @classmethod
    def _validate_start_urls(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("start_urls không được rỗng")
        for url in value:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError(f"start_urls chứa URL không hợp lệ: {url!r}")
        return value

    @field_validator("allowed_domains")
    @classmethod
    def _validate_allowed_domains(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("allowed_domains không được rỗng")
        return value


def _load_full_config() -> dict:
    """Đọc toàn bộ config.yaml hiện có trên đĩa (trả về {} nếu chưa tồn tại)."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@app.get("/config")
def get_config():
    full_config = _load_full_config()
    return {
        "start_urls": full_config.get("start_urls", []),
        "allowed_domains": full_config.get("allowed_domains", []),
        "content_selector": full_config.get("content_selector", ""),
        "title_selector": full_config.get("title_selector", ""),
        "max_pages": full_config.get("max_pages", 0),
    }


@app.post("/config")
def update_config(new_config: CrawlerConfig):
    if _crawl_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Không thể sửa config khi đang có crawl chạy. Hãy đợi crawl xong.",
        )

    # Giữ lại các field khác (delay, user_agent, ...) không quản lý qua API này.
    full_config = _load_full_config()
    full_config.update(new_config.model_dump())

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(full_config, f, allow_unicode=True, sort_keys=False)

    return full_config



