"""HTML 解析與欄位萃取工具。"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# 優先使用 lxml（快且容錯），若環境缺少則退回內建 parser
try:
    import lxml  # noqa: F401

    _DEFAULT_PARSER = "lxml"
except ImportError:  # pragma: no cover - 環境未安裝 lxml 時
    _DEFAULT_PARSER = "html.parser"


def make_soup(html: str | None, parser: str | None = None) -> BeautifulSoup:
    """把 HTML 字串轉成 BeautifulSoup 物件。"""
    return BeautifulSoup(html or "", parser or _DEFAULT_PARSER)


def resolve_url(base_url: str, href: str | None) -> str | None:
    """把相對連結轉成絕對 URL。"""
    if not href:
        return None
    return urljoin(base_url, href.strip())


def select_all(node: Any, selector: str | None) -> list:
    """安全地 select；selector 為空時回傳空清單。"""
    if not selector or node is None:
        return []
    return node.select(selector)


def _node_text(node: Any) -> str:
    """取得節點的文字（以空白串接、去除多餘空白）。"""
    return node.get_text(" ", strip=True)


def _attribute_value(node: Any, attribute: str | None) -> Any:
    """取得屬性值；class 這類多值屬性以空白串接。"""
    if not attribute:
        return None
    value = node.get(attribute)
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return value


def apply_transform(value: Any, transform: str | None) -> Any:
    """套用欄位轉換（int / float / strip / lower / upper）。"""
    if value is None or not transform:
        return value
    if transform == "strip":
        return value.strip() if isinstance(value, str) else value
    if transform == "lower":
        return value.lower() if isinstance(value, str) else value
    if transform == "upper":
        return value.upper() if isinstance(value, str) else value
    if transform == "int":
        cleaned = re.sub(r"[^\d-]", "", str(value))
        try:
            return int(cleaned)
        except ValueError:
            return None
    if transform == "float":
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        try:
            return float(cleaned)
        except ValueError:
            return None
    return value


def extract_field(node: Any, field: dict[str, Any]) -> Any:
    """依單一欄位設定，從節點萃取值。

    欄位設定範例：
        - name: price
          selector: "p.price_color"
          extract: text            # text | attribute | html
          attribute: null          # extract=attribute 時使用
          transform: null          # int | float | strip | lower | upper
          default: null            # 找不到時的回傳值
    """
    selector = field.get("selector")
    extract = field.get("extract", "text")

    element = node.select_one(selector) if (selector and node is not None) else node
    if element is None:
        return field.get("default")

    if extract == "text":
        value: Any = _node_text(element)
    elif extract == "attribute":
        value = _attribute_value(element, field.get("attribute"))
    elif extract == "html":
        value = element.decode_contents() if hasattr(element, "decode_contents") else str(element)
    else:
        value = _node_text(element)

    value = apply_transform(value, field.get("transform"))
    return value if value is not None else field.get("default")


def extract_fields(node: Any, fields: list[dict[str, Any]]) -> dict[str, Any]:
    """依欄位設定清單，萃取成一筆 dict。"""
    record: dict[str, Any] = {}
    for field in fields:
        record[field["name"]] = extract_field(node, field)
    return record
