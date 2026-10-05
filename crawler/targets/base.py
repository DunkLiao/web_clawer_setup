"""目標（Target）定義。

一個「目標」代表一個要爬取的網站 / 資料集。多數情況只要寫一個
config/targets/<name>.yaml 就夠了，不需要寫 Python；只有特殊邏輯
（例如需要清理欄位）才繼承 BaseTarget 覆寫方法。
"""
from __future__ import annotations

from typing import Any

from crawler.parser import (
    extract_field,
    make_soup,
    resolve_url,
    select_all,
)


# ----------------------------------------------------------------------
# 註冊表：讓目標名稱對應到 Python 類別（沒有註冊則使用 BaseTarget）
# ----------------------------------------------------------------------
_REGISTRY: dict[str, type["BaseTarget"]] = {}


def register(cls: type["BaseTarget"]) -> type["BaseTarget"]:
    """把目標類別註冊到 registry（可當裝飾器使用）。"""
    _REGISTRY[cls.name] = cls
    return cls


def registered(name: str) -> type["BaseTarget"] | None:
    return _REGISTRY.get(name)


class BaseTarget:
    """通用目標：完全由 YAML 設定驅動。

    子類別只要設定 `name` 並視需要覆寫 `extract_record` / `post_process` 即可。
    """

    name = "base"

    def __init__(
        self,
        config: dict[str, Any],
        settings: dict[str, Any],
        fetcher: Any,
        logger: Any,
    ):
        self.config = config or {}
        self.settings = settings or {}
        self.fetcher = fetcher
        self.logger = logger

        self.mode = str(self.config.get("mode", "detail")).lower()
        self.strategy = self.config.get("strategy")  # None = 沿用全域
        self.fields: list[dict[str, Any]] = self.config.get("fields", []) or []
        self.list_cfg: dict[str, Any] = self.config.get("list", {}) or {}

    # ------------------------------------------------------------------
    # 翻頁
    # ------------------------------------------------------------------
    def next_page_url(self, soup: Any, current_url: str) -> str | None:
        """next_link 模式：從目前頁面找出下一頁 URL。"""
        pagination = self.config.get("pagination", {}) or {}
        selector = pagination.get("next_selector")
        if not selector:
            return None
        anchor = soup.select_one(selector)
        if anchor is None:
            return None
        return resolve_url(current_url, anchor.get(pagination.get("next_attribute", "href")))

    # ------------------------------------------------------------------
    # 列表頁
    # ------------------------------------------------------------------
    def iter_items(self, soup: Any) -> list:
        """list 模式：回傳列表頁上的每個項目元素。"""
        return select_all(soup, self.list_cfg.get("item_selector"))

    def extract_links(self, soup: Any, page_url: str) -> list[str]:
        """detail 模式：回傳列表頁上每個項目的詳細頁連結（絕對 URL、去重）。"""
        item_selector = self.list_cfg.get("item_selector")
        link_selector = self.list_cfg.get("link_selector")
        link_attribute = self.list_cfg.get("link_attribute", "href")

        links: list[str] = []
        seen: set[str] = set()
        for item in select_all(soup, item_selector):
            anchor = None
            if link_selector:
                anchor = item.select_one(link_selector)
            elif getattr(item, "name", None) == "a":
                anchor = item
            else:
                anchor = item.find("a")
            if anchor is None:
                continue
            url = resolve_url(page_url, anchor.get(link_attribute))
            if url and url not in seen:
                seen.add(url)
                links.append(url)
        return links

    # ------------------------------------------------------------------
    # 欄位萃取
    # ------------------------------------------------------------------
    def extract_record(self, node: Any, base_url: str) -> dict[str, Any]:
        """從節點（list 模式的項目元素 / detail 模式的詳細頁）萃取一筆資料。"""
        record: dict[str, Any] = {}
        for field in self.fields:
            record[field["name"]] = extract_field(node, field)
        return self.post_process(record, base_url)

    def post_process(self, record: dict[str, Any], base_url: str) -> dict[str, Any]:
        """子類別可覆寫，做欄位清理 / 補值。預設不做任何事。"""
        return record
