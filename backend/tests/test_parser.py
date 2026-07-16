"""Tests cho parser + extractor (dùng HTML cố định)."""

from __future__ import annotations

from app.crawler.extractor import extract_items, get_next_page, parse_field_specs
from app.crawler.parser import FieldSpec, extract_jsonld, parse_html

SAMPLE_HTML = """<html><head>
<title>Test Page</title>
<script type="application/ld+json">{"@type":"Product","name":"X","price":"9.99","availability":"in stock","url":"https://x/p"}</script>
</head><body>
<article class="product">
  <h3><a href="/p1" title="Item One">Item One</a></h3>
  <span class="price">$10.00</span>
  <span class="stock" data-status="in">In stock</span>
</article>
<article class="product">
  <h3><a href="/p2" title="Item Two">Item Two</a></h3>
  <span class="price">$20.50</span>
  <span class="stock" data-status="out">Out</span>
</article>
<li class="next"><a href="/page-2">Next</a></li>
</body></html>"""


def test_parse_html_returns_parser() -> None:
    p = parse_html(SAMPLE_HTML)
    assert len(p.css("article.product")) == 2


def test_extract_items_with_container() -> None:
    specs = parse_field_specs(
        {
            "title": {"selector": "h3 a", "attr": "title", "type": "attr"},
            "price": {"selector": ".price", "type": "text", "transform": "price"},
            "availability": {"selector": ".stock", "attr": "data-status", "type": "attr"},
            "url": {"selector": "h3 a", "attr": "href", "type": "attr"},
        }
    )
    rows = extract_items(SAMPLE_HTML, "article.product", specs)
    assert len(rows) == 2
    assert rows[0]["title"] == "Item One"
    assert rows[0]["price"] == "10.00"  # price transform regex strips $ + dot trailing
    assert rows[0]["availability"] == "in"
    assert rows[1]["title"] == "Item Two"
    assert rows[1]["availability"] == "out"


def test_extract_items_without_container_root_level() -> None:
    specs = parse_field_specs(
        {
            "title": {"selector": "title", "type": "text", "transform": "strip"},
        }
    )
    rows = extract_items(SAMPLE_HTML, None, specs)
    assert len(rows) == 1
    assert rows[0]["title"] == "Test Page"


def test_get_next_page() -> None:
    nxt = get_next_page(SAMPLE_HTML, "li.next a::attr(href)", "https://x.com/page-1")
    assert nxt == "https://x.com/page-2"


def test_get_next_page_missing() -> None:
    assert get_next_page(SAMPLE_HTML, ".nope::attr(href)", "https://x.com/") is None


def test_jsonld_extraction() -> None:
    ld = extract_jsonld(parse_html(SAMPLE_HTML))
    assert len(ld) == 1
    assert ld[0]["@type"] == "Product"
    assert ld[0]["name"] == "X"


def test_fieldspec_regex_extraction() -> None:
    p = parse_html(SAMPLE_HTML)
    node = p.css_first("article.product")
    spec = FieldSpec(selector=".price", type="text", regex=r"\d+\.\d+")
    val = __import__("app.crawler.parser", fromlist=["extract_field"]).extract_field(node, spec)
    assert val == "10.00"


def test_fieldspec_int_transform() -> None:
    p = parse_html('<div class="qty">1,234</div>')
    node = p.css_first("body")
    spec = FieldSpec(selector=".qty", type="text", transform="int")
    val = __import__("app.crawler.parser", fromlist=["extract_field"]).extract_field(node, spec)
    assert val == 1234
