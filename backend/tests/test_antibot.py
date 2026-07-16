"""Tests cho antibot Cloudflare detection."""

from __future__ import annotations

import httpx

from app.crawler.antibot import is_cloudflare_challenge


def _mk_response(status: int, text: str = "", server: str = "") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        text=text,
        request=httpx.Request("GET", "https://x.com/"),
        headers=httpx.Headers({"server": server} if server else {}),
    )


def test_cf_challenge_by_403_just_a_moment() -> None:
    r = _mk_response(403, "<title>Just a moment...</title>")
    assert is_cloudflare_challenge(r) is True


def test_cf_challenge_by_503_cf_mitigated() -> None:
    r = httpx.Response(
        503,
        text="<title>just checking</title>",
        request=httpx.Request("GET", "https://x.com/"),
        headers=httpx.Headers({"cf-mitigated": "challenge", "server": "cloudflare"}),
    )
    assert is_cloudflare_challenge(r) is True


def test_not_cf_if_403_without_markers() -> None:
    r = _mk_response(403, "<title>Forbidden</title>")
    assert is_cloudflare_challenge(r) is False


def test_not_cf_if_200() -> None:
    r = _mk_response(200, "<html>OK</html>")
    assert is_cloudflare_challenge(r) is False


def test_cf_challenge_platform_marker() -> None:
    r = _mk_response(
        503, '<script src="/cdn-cgi/challenge-platform/h/g/orchestrate/jsch/v1"></script>'
    )
    assert is_cloudflare_challenge(r) is True
