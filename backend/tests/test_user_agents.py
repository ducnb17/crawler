"""Tests cho user_agents module — không require network/fake-useragent."""

from __future__ import annotations

from app.crawler import user_agents


def test_random_ua_returns_string() -> None:
    ua = user_agents.get_random_user_agent()
    assert isinstance(ua, str)
    assert len(ua) > 20
    assert "Mozilla" in ua


def test_random_header_has_required_keys() -> None:
    h = user_agents.get_random_header()
    assert "User-Agent" in h
    assert "Accept" in h
    assert "Accept-Language" in h
    assert "Accept-Encoding" in h
    # brotli không được phép vì lib chưa cài
    assert "br" not in h["Accept-Encoding"]
    assert "Connection" in h


def test_random_header_rotation() -> None:
    seen: set[str] = set()
    for _ in range(40):
        seen.add(user_agents.get_random_user_agent())
    # Phải có rotation (vì pool có ≥9 fallback + fake_useragent nếu có)
    assert len(seen) >= 3


def test_sec_ch_ua_for_firefox_empty() -> None:
    firefox = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0"
    assert user_agents._build_sec_ch_ua(firefox) == {}


def test_sec_ch_ua_for_chrome() -> None:
    chrome = "Mozilla/5.0 ... Chrome/131.0.0.0 Safari/537.36"
    sec = user_agents._build_sec_ch_ua(chrome)
    assert "Sec-Ch-Ua" in sec
    assert "131" in sec["Sec-Ch-Ua"]
    assert sec["Sec-Ch-Ua-Mobile"] == "?0"
    assert (
        sec["Sec-Ch-Ua-Platform"] == '"Unknown"'
    )  # no Windows/Mac/Linux keyword present in test UA
