"""Cloudflare detection (header + body markers). Dùng chung cho fetcher + middleware."""

from __future__ import annotations

import httpx

CLOUDFLARE_MARKERS: tuple[str, ...] = (
    "just a moment",
    "cf_chl_opt",
    "cf-chl",
    "challenge-platform",
    "checking your browser",
    "ddg-protection",
    "cloudflare-static/email-decode",
)


def is_cloudflare_challenge(response: httpx.Response) -> bool:
    if response.status_code not in (403, 503, 429):
        return False
    headers = response.headers
    # Header hint mạnh (Cloudflare nói rõ là đang challenge) → không cần body marker
    if headers.get("cf-mitigated") or headers.get("server", "").lower().startswith("cloudflare"):
        # cf-mitigated="challenge" / cf-chl-bypass header là signal đủ
        if headers.get("cf-mitigated"):
            return True
        text = response.text[:5000].lower()
        return any(m in text for m in CLOUDFLARE_MARKERS)
    text = response.text[:5000].lower()
    return any(m in text for m in CLOUDFLARE_MARKERS)
    text = response.text[:5000].lower()
    return any(m in text for m in CLOUDFLARE_MARKERS)
