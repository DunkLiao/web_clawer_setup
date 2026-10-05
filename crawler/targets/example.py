"""範例目標：books.toscrape.com。

這個檔案示範「多數網站靠 example.yaml 即可，只有特殊欄位清理才用 Python」。

yaml 的 rating 欄位抓到的 class 值形如 "star-rating Three"，
這裡把它轉成 1-5 的整數。
"""
from __future__ import annotations

from typing import Any

from crawler.targets.base import BaseTarget, register

_RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


@register
class ExampleTarget(BaseTarget):
    name = "example"

    def post_process(self, record: dict[str, Any], base_url: str) -> dict[str, Any]:
        rating = str(record.get("rating") or "").lower()
        for word, value in _RATING_WORDS.items():
            if word in rating:
                record["rating"] = value
                break
        return record
