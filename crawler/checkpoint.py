"""斷點續爬狀態管理。

在 checkpoint 目錄下為每個目標維護三個 append-only 檔案：
- <目標>.done_urls.txt  ：已完成的「詳細頁」URL（每行一個）
- <目標>.done_pages.txt ：已完成的「列表頁」URL
- <目標>.records.jsonl  ：已抓取的資料（每行一筆 JSON）

好處：讀取一次載入記憶體、寫入時 append（O(1)），可支撐數千頁規模，
中斷後重跑會自動跳過已完成的部分。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Checkpoint:
    def __init__(self, directory: Path | str, target_name: str, enabled: bool = True):
        self.dir = Path(directory)
        self.target = target_name
        self.enabled = enabled

        self.urls_file = self.dir / f"{target_name}.done_urls.txt"
        self.pages_file = self.dir / f"{target_name}.done_pages.txt"
        self.records_file = self.dir / f"{target_name}.records.jsonl"

        self._done: set[str] = set()
        self._done_pages: set[str] = set()
        self._records: list[dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.enabled:
            return
        self._done = self._read_lines(self.urls_file)
        self._done_pages = self._read_lines(self.pages_file)
        if self.records_file.exists():
            with self.records_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    @staticmethod
    def _read_lines(path: Path) -> set[str]:
        if not path.exists():
            return set()
        with path.open("r", encoding="utf-8") as handle:
            return {line.strip() for line in handle if line.strip()}

    # ------------------------------------------------------------------
    @property
    def record_count(self) -> int:
        return len(self._records)

    def all_records(self) -> list[dict[str, Any]]:
        return self._records

    # --- 詳細頁 ---
    def is_done(self, url: str) -> bool:
        return self.enabled and url in self._done

    def mark_done(self, url: str) -> None:
        if not self.enabled or url in self._done:
            return
        self._done.add(url)
        self._append_line(self.urls_file, url)

    # --- 列表頁 ---
    def is_page_done(self, page_url: str) -> bool:
        return self.enabled and page_url in self._done_pages

    def mark_page_done(self, page_url: str) -> None:
        if not self.enabled or page_url in self._done_pages:
            return
        self._done_pages.add(page_url)
        self._append_line(self.pages_file, page_url)

    # --- 資料 ---
    def add_record(self, record: dict[str, Any]) -> None:
        self._records.append(record)
        if self.enabled:
            self._append_line(
                self.records_file, json.dumps(record, ensure_ascii=False)
            )

    # --- 重置 ---
    def reset(self) -> None:
        for path in (self.urls_file, self.pages_file, self.records_file):
            if path.exists():
                path.unlink()
        self._done.clear()
        self._done_pages.clear()
        self._records.clear()

    # ------------------------------------------------------------------
    @staticmethod
    def _append_line(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
