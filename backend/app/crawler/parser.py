"""Parser: parse HTML (selectolax nhanh) + hỗ trợ CSS, XPath, regex, attr extract.
Ngoài ra còn trích JSON-LD/schema.org microdata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from selectolax.parser import HTMLParser

JSONLD_BLOCK_RE = re.compile(r"application/ld\+json", re.I)


@dataclass(slots=True)
class FieldSpec:
    """Cấu hình trích 1 trường từ item container."""

    selector: str
    attr: str | None = None  # None => text content
    type: str = "text"  # text|attr|html|regex|jsonld
    regex: str | None = None
    transform: str | None = None  # strip|lower|upper|int|float|price


def parse_html(html: str | bytes) -> HTMLParser:
    return HTMLParser(html)


def query_container_count(html: HTMLParser, container: str) -> int:
    return len(html.css(container))


def extract_field(container_node: Any, spec: FieldSpec) -> Any:
    """Trích 1 field từ 1 node container."""
    # XPath support: bắt đầu bằng "xpath:="
    if spec.selector.startswith("xpath:"):
        return None  # selectolax không hỗ trợ xpath trực tiếp; yêu cầu lxml
    node = container_node.css_first(spec.selector)
    if node is None:
        return None
    if spec.type == "attr" or spec.attr:
        val = node.attributes.get(spec.attr) if spec.attr else None
    elif spec.type == "html":
        val = node.html
    else:  # text
        val = node.text(strip=True)
    if val is None:
        return None
    if spec.regex:
        m = re.search(spec.regex, str(val))
        val = m.group(0) if m else None
    if val is not None:
        val = _apply_transform(val, spec.transform)
    return val


def _apply_transform(val: Any, transform: str | None) -> Any:
    if transform is None:
        return val
    t = transform.lower()
    s = str(val)
    if t == "strip":
        return s.strip()
    if t == "lower":
        return s.lower()
    if t == "upper":
        return s.upper()
    if t == "int":
        m = re.search(r"-?\d+", s.replace(",", ""))
        return int(m.group()) if m else None
    if t == "float":
        m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
        return float(m.group()) if m else None
    if t == "price":
        m = re.search(r"[\d.,]+", s)
        return m.group().replace(",", "") if m else None
    return val


def extract_jsonld(html: HTMLParser) -> list[dict[str, Any]]:
    """Trích mọi JSON-LD block trong <script type=application/ld+json>."""
    out: list[dict[str, Any]] = []
    for script in html.css("script"):
        if JSONLD_BLOCK_RE.search(script.attributes.get("type") or ""):
            try:
                data = json.loads(script.text())
                if isinstance(data, list):
                    out.extend(x for x in data if isinstance(x, dict))
                elif isinstance(data, dict):
                    # có thể @graph
                    if "@graph" in data and isinstance(data["@graph"], list):
                        out.extend(x for x in data["@graph"] if isinstance(x, dict))
                    else:
                        out.append(data)
            except Exception:
                continue
    return out


def resolve_next_page(html: HTMLParser, selector: str, base_url: str) -> str | None:
    """Trích URL trang kế nếu có."""
    if not selector:
        return None
    # Hỗ trợ "css::attr(href)" hoặc "::attr(href)"
    sel, _, attr = selector.partition("::attr(")
    attr = attr.rstrip(")")
    node = None
    if sel:
        node = html.css_first(sel.strip())
    if node is None:
        return None
    href = node.attributes.get(attr or "href")
    if not href:
        return None
    from urllib.parse import urljoin

    return urljoin(base_url, href)
