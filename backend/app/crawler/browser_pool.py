"""Playwright browser/context pool — chia sẻ 1 browser cho nhiều context
để tiết kiệm RAM."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.config import get_settings
from app.core.logging import logger

_browser: Any = None
_browser_lock = asyncio.Lock()
_contexts: list[Any] = []
_pool_sem: asyncio.Semaphore | None = None


async def _ensure_browser() -> Any:
    global _browser, _browser_lock, _pool_sem
    if _browser is not None:
        return _browser
    async with _browser_lock:
        if _browser is not None:
            return _browser
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        _pool_sem = asyncio.Semaphore(get_settings().crawler_browser_pool_size)
        logger.info("browser_pool_started", size=get_settings().crawler_browser_pool_size)
        return _browser


async def shutdown_browser() -> None:
    global _browser, _contexts, _pool_sem
    if _browser is not None:
        try:
            await _browser.close()
        except Exception as e:
            logger.debug("browser_close_failed", error=str(e))
    _browser = None
    _contexts.clear()
    _pool_sem = None


@asynccontextmanager
async def acquire_context(
    proxy: str | None = None, extra_headers: dict[str, str] | None = None
) -> AsyncIterator[Any]:
    """Lấy 1 Playwright context từ pool. Tạo+mỗi lần (cheap hơn page) và close sau."""
    await _ensure_browser()
    assert _pool_sem is not None
    async with _pool_sem:
        context = await _browser.new_context(  # type: ignore[union-attr]
            viewport={"width": 1280, "height": 720},
            user_agent=None,
            extra_http_headers=extra_headers or {},
            proxy={"server": proxy} if proxy else None,
        )
        try:
            # Anti-detection cơ bản
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            yield context
        finally:
            try:
                await context.close()
            except Exception as e:
                logger.debug("context_close_failed", error=str(e))
