"""Extractor: từ FieldSpec config của job → tạo dict row. Xử lý JSON-LD fallback."""

from __future__ import annotations

from typing import Any

from app.core.logging import logger
from app.crawler.parser import (
    FieldSpec,
    extract_field,
    extract_jsonld,
    parse_html,
    resolve_next_page,
)


def parse_field_specs(fields_cfg: dict[str, Any]) -> dict[str, FieldSpec]:
    """Chuyển config JSON → FieldSpec objects."""
    specs: dict[str, FieldSpec] = {}
    for name, cfg in fields_cfg.items():
        if not isinstance(cfg, dict) or "selector" not in cfg:
            continue
        specs[name] = FieldSpec(
            selector=cfg["selector"],
            attr=cfg.get("attr"),
            type=cfg.get("type", "text"),
            regex=cfg.get("regex"),
            transform=cfg.get("transform"),
        )
    return specs


def extract_items(
    html_text: str | bytes,
    container: str | None,
    field_specs: dict[str, FieldSpec],
) -> list[dict[str, Any]]:
    """Trích list item từ HTML. Nếu không có container → 1 item duy nhất từ root."""
    html = parse_html(html_text)
    items: list[dict[str, Any]] = []
    if container:
        nodes = html.css(container)
        for node in nodes:
            row = _extract_one(node, field_specs)
            if row:
                items.append(row)
    else:
        # Single-page extract (selector có thể ở <head> như title/meta)
        row = _extract_one(html, field_specs)
        if row:
            items.append(row)
    return items


def _extract_one(node: Any, field_specs: dict[str, FieldSpec]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for name, spec in field_specs.items():
        try:
            row[name] = extract_field(node, spec)
        except Exception as e:
            logger.debug("extract_field_error", field=name, error=str(e))
            row[name] = None
    # JSON-LD bổ sung nếu thiếu
    return row


def extract_jsonld_into(
    items: list[dict[str, Any]], html_text: str | bytes
) -> list[dict[str, Any]]:
    """Bổ sung giá trị thiếu trong items từ JSON-LD schema.org."""
    html = parse_html(html_text)
    ld = extract_jsonld(html)
    if not ld:
        return items
    # Map phổ biến: Product/Article/Event
    for i, item in enumerate(items):
        if i < len(ld):
            _fill_from_jsonld(item, ld[i])
        else:
            break
    return items


_LD_FIELD_MAP = {
    "Product": {
        "title": "name",
        "name": "name",
        "price": "price",
        "description": "description",
        "availability": "availability",
        "url": "url",
        "image": "image",
    },
    "Article": {
        "title": "headline",
        "name": "headline",
        "description": "description",
        "author": "author",
        "datePublished": "datePublished",
        "url": "url",
    },
    "Event": {
        "title": "name",
        "name": "name",
        "description": "description",
        "startDate": "startDate",
        "location": "location",
    },
}


def _fill_from_jsonld(item: dict[str, Any], ld: dict[str, Any]) -> None:
    type_ = ld.get("@type", "")
    mapping = _LD_FIELD_MAP.get(type_)
    if not mapping:
        return
    for item_key, ld_key in mapping.items():
        if not item.get(item_key) and ld.get(ld_key) is not None:
            item[item_key] = ld.get(ld_key)


def jsonld_total(html_text: str | bytes) -> int:
    return len(extract_jsonld(parse_html(html_text)))


def get_next_page(html_text: str | bytes, selector: str, base_url: str) -> str | None:
    html = parse_html(html_text)
    return resolve_next_page(html, selector, base_url)
