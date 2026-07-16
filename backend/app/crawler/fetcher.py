"""Async Fetcher: httpx (with retry/backoff) → cloudscraper fallback (CF) → optional Playwright.

Đây là primitive nặng nhất của engine. Mọi HTTP request đi qua đây.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings
from app.core.logging import logger
from app.crawler.antibot import is_cloudflare_challenge
from app.crawler.browser_pool import acquire_context
from app.crawler.user_agents import get_random_header

# Status codes cần retry tạm thời
RETRYABLE_STATUS: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504, 520, 522, 524})


@dataclass(slots=True)
class FetchResult:
    url: str
    status: int
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: int = 0
    from_fallback: str = ""  # "" | "cloudscraper" | "playwright"
    proxy_used: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    @property
    def content(self) -> str:
        return self.text


class Fetcher:
    """Async fetch primitive.

    Order:
    1. httpx.AsyncClient (retry với backoff) — UA rotation + optional proxy.
    2. Nếu Cloudflare challenge → cloudscraper trong `asyncio.to_thread` (lib sync).
    3. Nếu `force_render=True` (job.render_js=True) hoặc content thiếu → Playwright.
    """

    def __init__(
        self,
        *,
        timeout: int | None = None,
        max_retries: int | None = None,
        backoff_cap: int | None = None,
        proxy: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        s = get_settings()
        self.timeout = timeout or s.crawler_download_timeout
        self.max_retries = max_retries or s.crawler_max_retries
        self.backoff_cap = backoff_cap or s.crawler_backoff_cap
        self.proxy = proxy
        self.extra_headers = extra_headers or {}
        self._cloudscraper = None
        if s.antibot_use_cloudscraper:
            self._cloudscraper = self._init_cloudscraper()

    @staticmethod
    def _init_cloudscraper() -> Any:
        import cloudscraper

        return cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
            delay=10,
        )

    # ===== Public =====
    async def fetch(
        self,
        url: str,
        *,
        force_render: bool = False,
        min_content_length: int = 0,
        render_wait: str | None = None,
    ) -> FetchResult:
        """Fetch 1 URL; fallback tự động."""
        result = await self._httpx_fetch(url)
        if not result.ok:
            # Cloudflare detection trước khi retry bằng cloudscraper
            if (
                result.status in (403, 503)
                and self._cloudscraper is not None
                and is_cloudflare_challenge(_mk_response_like(result))
            ):
                logger.info("cloudflare_fallback", url=url, status=result.status)
                cs_result = await self._cloudscraper_fetch(url)
                if cs_result.ok:
                    return cs_result
            return result
        # content insufficient → playwright fallback
        need_render = force_render or (min_content_length and len(result.text) < min_content_length)
        if need_render:
            logger.info(
                "playwright_fallback", url=url, content_len=len(result.text), force=force_render
            )
            try:
                pw_result = await self._playwright_fetch(url, wait_selector=render_wait)
                if pw_result.ok and len(pw_result.text) > len(result.text):
                    return pw_result
            except Exception as e:
                logger.warning("playwright_fallback_failed", url=url, error=str(e))
        return result

    # ===== 1. httpx path =====
    async def _httpx_fetch(self, url: str) -> FetchResult:
        client_kwargs: dict[str, Any] = {
            "timeout": self.timeout,
            "follow_redirects": True,
            "http2": True,
            "headers": {**get_random_header(), **self.extra_headers},
        }
        if self.proxy:
            client_kwargs["proxy"] = self.proxy

        last_err: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    response = await client.get(url)
                if response.status_code in RETRYABLE_STATUS and attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue
                return FetchResult(
                    url=str(response.request.url),
                    status=response.status_code,
                    text=response.content.decode(response.encoding or "utf-8", errors="replace"),
                    headers=dict(response.headers),
                    elapsed_ms=int(response.elapsed.total_seconds() * 1000),
                )
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue
                logger.warning("httpx_fetch_exhausted", url=url, error=last_err)
                return FetchResult(url=url, status=0, error=last_err, proxy_used=self.proxy)
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                logger.warning("httpx_fetch_unexpected", url=url, error=last_err)
                return FetchResult(url=url, status=0, error=last_err, proxy_used=self.proxy)
        return FetchResult(url=url, status=0, error=last_err or "exhausted", proxy_used=self.proxy)

    async def _backoff(self, attempt: int) -> None:
        delay = min(self.backoff_cap, 2**attempt) + random.uniform(0, 1.0)
        await asyncio.sleep(delay)

    # ===== 2. cloudscraper path (sync → to_thread) =====
    async def _cloudscraper_fetch(self, url: str) -> FetchResult:
        cs = self._cloudscraper
        if cs is None:
            return FetchResult(url=url, status=0, error="cloudscraper_disabled")
        import time

        def _do() -> FetchResult:
            t0 = time.monotonic()
            try:
                resp = cs.get(url, timeout=self.timeout)
                return FetchResult(
                    url=str(resp.url),
                    status=int(resp.status_code),
                    text=resp.text or "",
                    headers=dict(resp.headers),
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    from_fallback="cloudscraper",
                    proxy_used=self.proxy,
                )
            except Exception as e:
                return FetchResult(
                    url=url, status=0, error=f"cloudscraper: {e}", from_fallback="cloudscraper"
                )

        return await asyncio.to_thread(_do)

    # ===== 3. Playwright path =====
    async def _playwright_fetch(self, url: str, wait_selector: str | None = None) -> FetchResult:
        import time

        async with acquire_context(proxy=self.proxy, extra_headers=self.extra_headers) as ctx:
            page = await ctx.new_page()
            try:
                t0 = time.monotonic()
                resp = await page.goto(
                    url, timeout=self.timeout * 1000, wait_until="domcontentloaded"
                )
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=self.timeout * 1000)
                    except Exception as e:
                        logger.debug("playwright_wait_failed", url=url, error=str(e))
                html = await page.content()
                status = int(resp.status) if resp else 200
                headers: dict[str, str] = {}
                if resp:
                    for k, v in resp.headers.items():
                        headers[k] = v
                return FetchResult(
                    url=url,
                    status=status,
                    text=html,
                    headers=headers,
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    from_fallback="playwright",
                    proxy_used=self.proxy,
                )
            finally:
                try:
                    await page.close()
                except Exception as e:
                    logger.debug("playwright_page_close_failed", error=str(e))


def _mk_response_like(result: FetchResult) -> httpx.Response:
    """Tạo httpx.Response tạm để dùng is_cloudflare_challenge()."""
    req = httpx.Request("GET", result.url)
    return httpx.Response(
        status_code=result.status or 599,
        request=req,
        text=result.text,
        headers=httpx.Headers(result.headers),
    )
