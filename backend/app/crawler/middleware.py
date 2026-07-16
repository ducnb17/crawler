"""Pluggable middleware hooks (request/response). Hook có thể modify request headers,
short-circuit,肝病用药 retry, log..."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class RequestHook(Protocol):
    async def __call__(self, request: httpx.Request, ctx: dict[str, Any]) -> None: ...


class ResponseHook(Protocol):
    async def __call__(self, response: httpx.Response, ctx: dict[str, Any]) -> None: ...


@dataclass(slots=True)
class Middleware:
    request_hooks: list[RequestHook] | None = None
    response_hooks: list[ResponseHook] | None = None


class HookChain:
    """Tập hợp hooks có thể modify request trước khi gửi và inspect response sau."""

    def __init__(self) -> None:
        self._req: list[RequestHook] = []
        self._res: list[ResponseHook] = []

    def add_request(self, hook: RequestHook) -> None:
        self._req.append(hook)

    def add_response(self, hook: ResponseHook) -> None:
        self._res.append(hook)

    async def run_request(self, request: httpx.Request, ctx: dict[str, Any]) -> None:
        for hook in self._req:
            try:
                await hook(request, ctx)
            except Exception as e:
                ctx.setdefault("errors", []).append({"phase": "request", "error": str(e)})

    async def run_response(self, response: httpx.Response, ctx: dict[str, Any]) -> None:
        for hook in self._res:
            try:
                await hook(response, ctx)
            except Exception as e:
                ctx.setdefault("errors", []).append({"phase": "response", "error": str(e)})
