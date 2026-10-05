"""爬取流程編排：翻頁、重試、checkpoint、輸出。

流程（detail 模式）：
    列表頁 -> 取得項目連結 -> 逐一到詳細頁抓取 -> 萃取欄位 -> checkpoint -> 輸出
流程（list 模式）：
    列表頁 -> 逐項目萃取欄位 -> checkpoint -> 輸出
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterator

from crawler.checkpoint import Checkpoint
from crawler.parser import make_soup
from crawler.storage import Storage


class CrawlerEngine:
    def __init__(
        self,
        target: Any,
        fetcher: Any,
        settings: dict[str, Any],
        logger: Any,
        project_root: Path,
    ):
        self.target = target
        self.fetcher = fetcher
        self.settings = settings
        self.logger = logger
        self.project_root = Path(project_root)

        run_cfg = settings.get("run", {}) or {}
        out_cfg = settings.get("output", {}) or {}
        cp_cfg = settings.get("checkpoint", {}) or {}
        fetch_cfg = settings.get("fetch", {}) or {}

        self.max_pages = int(run_cfg.get("max_pages", 0) or 0)
        self.stop_on_error = bool(run_cfg.get("stop_on_error", False))

        self.retries = int(fetch_cfg.get("retries", 3) or 0)
        self.backoff = list(fetch_cfg.get("retry_backoff", [5, 15, 45]) or [])

        out_dir = self._resolve(out_cfg.get("dir", "data/output"))
        self.storage = Storage(
            out_dir,
            fmt=out_cfg.get("format", "xlsx"),
            add_timestamp=bool(out_cfg.get("add_timestamp", True)),
        )

        cp_dir = self._resolve(cp_cfg.get("dir", "data/checkpoints"))
        self.checkpoint = Checkpoint(
            cp_dir, target.name, enabled=bool(cp_cfg.get("enabled", True))
        )

    # ------------------------------------------------------------------
    def _resolve(self, path: str | Path) -> Path:
        path = Path(path)
        return path if path.is_absolute() else (self.project_root / path)

    # ------------------------------------------------------------------
    def run(self, fresh: bool = False) -> Path | None:
        target = self.target
        logger = self.logger
        checkpoint = self.checkpoint

        if fresh:
            checkpoint.reset()
            logger.info("已清除 checkpoint，重新開始")

        logger.info("目標：%s（模式：%s，策略：%s）", target.name, target.mode, target.strategy or "auto")

        pages_done = 0
        new_items = 0

        for page_url, html in self._page_iter():
            if self.max_pages and pages_done >= self.max_pages:
                logger.info("已達 max_pages=%d，停止翻頁", self.max_pages)
                break

            if checkpoint.is_page_done(page_url):
                logger.info("略過已完成的頁面：%s", page_url)
                continue

            soup = make_soup(html)

            if target.mode == "list":
                count = self._process_list_page(soup, page_url)
            else:
                count = self._process_detail_page(soup, page_url)

            checkpoint.mark_page_done(page_url)
            pages_done += 1
            new_items += count
            logger.info("頁面完成：%s（本次新增 %d 筆，累計 %d 筆）", page_url, count, checkpoint.record_count)

        records = checkpoint.all_records()
        logger.info("執行結束：共 %d 頁、%d 筆資料", pages_done, len(records))
        if not records:
            logger.warning("沒有抓到任何資料")
            return None

        path = self.storage.save(records, target.name)
        logger.info("已輸出：%s", path)
        return path

    # ------------------------------------------------------------------
    # list 模式
    # ------------------------------------------------------------------
    def _process_list_page(self, soup: Any, page_url: str) -> int:
        count = 0
        for item in self.target.iter_items(soup):
            record = self.target.extract_record(item, page_url)
            record.setdefault("_source_url", page_url)
            self.checkpoint.add_record(record)
            count += 1
        return count

    # ------------------------------------------------------------------
    # detail 模式
    # ------------------------------------------------------------------
    def _process_detail_page(self, soup: Any, page_url: str) -> int:
        links = self.target.extract_links(soup, page_url)
        self.logger.info("找到 %d 個項目連結：%s", len(links), page_url)
        count = 0
        for link in links:
            if self.checkpoint.is_done(link):
                continue
            html = self._fetch(link)
            if html is None:
                if self.stop_on_error:
                    break
                continue
            record = self.target.extract_record(make_soup(html), link)
            record.setdefault("_source_url", link)
            self.checkpoint.add_record(record)
            self.checkpoint.mark_done(link)
            count += 1
        return count

    # ------------------------------------------------------------------
    # 翻頁：產生 (page_url, html)
    # ------------------------------------------------------------------
    def _page_iter(self) -> Iterator[tuple[str, str]]:
        config = self.target.config
        pagination = config.get("pagination", {}) or {}
        ptype = str(pagination.get("type", "single")).lower()
        start_url = config.get("start_url")
        if not start_url:
            raise ValueError("目標設定缺少 start_url")

        if ptype == "single":
            html = self._fetch(start_url)
            if html is not None:
                yield start_url, html
            return

        if ptype == "url_pattern":
            pattern = pagination.get("pattern")
            if not pattern:
                raise ValueError("pagination.type=url_pattern 需要 pattern")
            start_page = int(pagination.get("start_page", 1))
            max_pages = int(pagination.get("max_pages", 1) or 1)
            for index in range(start_page, start_page + max_pages):
                url = pattern.format(page=index)
                if self.checkpoint.is_page_done(url):
                    self.logger.info("略過已完成的頁面：%s", url)
                    continue
                html = self._fetch(url)
                if html is None:
                    if self.stop_on_error:
                        return
                    continue
                yield url, html
            return

        if ptype == "next_link":
            url: str | None = start_url
            page = 0
            max_pages = int(pagination.get("max_pages", 0) or 0)
            while url:
                if max_pages and page >= max_pages:
                    break
                html = self._fetch(url)
                if html is None:
                    if self.stop_on_error:
                        return
                    break
                yield url, html
                page += 1
                url = self.target.next_page_url(make_soup(html), url)
            return

        raise ValueError(f"未知的 pagination type：{ptype}")

    # ------------------------------------------------------------------
    # 抓取 + 重試（指數退避）
    # ------------------------------------------------------------------
    def _fetch(self, url: str) -> str | None:
        attempt = 0
        while True:
            try:
                return self.fetcher.fetch(url, strategy=self.target.strategy)
            except Exception as exc:  # noqa: BLE001
                attempt += 1
                if attempt > self.retries:
                    self.logger.error("抓取失敗（已重試 %d 次）：%s -> %s", self.retries, url, exc)
                    return None
                wait = self.backoff[min(attempt - 1, len(self.backoff) - 1)] if self.backoff else 5
                self.logger.warning(
                    "抓取失敗（第 %d 次）：%s -> %s，%s 秒後重試", attempt, url, exc, wait
                )
                time.sleep(wait)
