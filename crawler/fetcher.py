"""雙策略抓取器。

- 靜態優先：requests + BeautifulSoup（快）
- 動態 fallback：Playwright（處理 JS 渲染 / 反爬）
- strategy = auto 時，先試靜態，偵測到內容需要 JS 才改用 Playwright
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from crawler.parser import make_soup


class FetchError(Exception):
    """抓取失敗。"""


# 這些是本機設定，避免 playwright 匯入失敗時影響靜態抓取
class Fetcher:
    def __init__(self, fetch_cfg: dict[str, Any], browser_cfg: dict[str, Any], logger: logging.Logger):
        self.logger = logger
        self.strategy = str(fetch_cfg.get("strategy", "auto")).lower()
        self.delay_min = float(fetch_cfg.get("delay_min", 1.0) or 0.0)
        self.delay_max = float(fetch_cfg.get("delay_max", 3.0) or 0.0)
        self.timeout = float(fetch_cfg.get("timeout", 30) or 30)
        self.user_agent = fetch_cfg.get("user_agent") or "Mozilla/5.0 (compatible; WebCrawlerSetup/0.1)"
        self.headless = bool(browser_cfg.get("headless", True))
        self.respect_robots = bool(fetch_cfg.get("respect_robots", True))

        self._session: requests.Session | None = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._request_count = 0
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    # ------------------------------------------------------------------
    # 對外介面
    # ------------------------------------------------------------------
    def fetch(self, url: str, strategy: str | None = None) -> str:
        """抓取單一 URL 並回傳 HTML。

        strategy 參數可覆寫全域策略（目標層級設定）。
        """
        strategy = (strategy or self.strategy).lower()
        self._throttle()

        if not self._robots_allows(url):
            raise FetchError(f"robots.txt 不允許抓取：{url}")

        if strategy == "static":
            return self._fetch_static(url)
        if strategy == "dynamic":
            return self._fetch_dynamic(url)

        # auto：靜態優先
        try:
            html = self._fetch_static(url)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("靜態抓取失敗（%s），改用 Playwright：%s", exc, url)
            return self._fetch_dynamic(url)

        if self._needs_dynamic(html):
            self.logger.info("偵測到頁面需動態渲染，改用 Playwright：%s", url)
            return self._fetch_dynamic(url)

        return html

    def close(self) -> None:
        """釋放資源。"""
        try:
            if self._context is not None:
                self._context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = self._browser = self._playwright = None
        if self._session is not None:
            self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # 內部：robots.txt 合規檢查
    # ------------------------------------------------------------------
    def _robots_allows(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots_cache.get(base, "missing")
        if parser == "missing":
            parser = self._load_robots(base)
            self._robots_cache[base] = parser
        if parser is None:
            return True  # 無法取得 robots.txt 時預設允許
        return parser.can_fetch(self.user_agent, url)

    def _load_robots(self, base_url: str) -> RobotFileParser | None:
        robots_url = base_url.rstrip("/") + "/robots.txt"
        try:
            session = self._ensure_session()
            response = session.get(robots_url, timeout=min(self.timeout, 15))
            if response.status_code >= 400:
                return None  # 沒有 robots.txt = 允許
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("無法取得 robots.txt（%s）：%s", robots_url, exc)
            return None

    # ------------------------------------------------------------------
    # 內部：速率控制
    # ------------------------------------------------------------------
    def _throttle(self) -> None:
        self._request_count += 1
        if self._request_count == 1:
            return  # 第一個請求不延遲
        if self.delay_max <= 0 and self.delay_min <= 0:
            return
        low, high = sorted((self.delay_min, self.delay_max))
        time.sleep(random.uniform(low, high))

    # ------------------------------------------------------------------
    # 內部：靜態抓取
    # ------------------------------------------------------------------
    def _ensure_session(self) -> requests.Session:
        if self._session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                }
            )
            self._session = session
        return self._session

    def _fetch_static(self, url: str) -> str:
        session = self._ensure_session()
        response = session.get(url, timeout=self.timeout)
        if response.status_code >= 400:
            raise FetchError(f"HTTP {response.status_code}")
        # requests 對沒有 charset 的 text/* 會假定 ISO-8859-1，這裡修正編碼
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def _needs_dynamic(self, html: str) -> bool:
        """啟發式判斷：靜態 HTML 是否幾乎沒有內容（可能靠 JS 渲染）。"""
        if not html or len(html.strip()) < 500:
            return True
        try:
            soup = make_soup(html)
        except Exception:  # noqa: BLE001
            return False
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        return len(text) < 120

    # ------------------------------------------------------------------
    # 內部：動態抓取（Playwright）
    # ------------------------------------------------------------------
    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise FetchError(
                "需要 Playwright 才能動態抓取，請先執行 install_playwright.bat"
            ) from exc

        self.logger.info("啟動 Playwright 瀏覽器（headless=%s）", self.headless)
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            user_agent=self.user_agent,
            locale="zh-TW",
        )

    def _fetch_dynamic(self, url: str) -> str:
        self._ensure_browser()
        assert self._context is not None
        page = self._context.new_page()
        try:
            page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:  # noqa: BLE001
                # 有些站台永遠不會 networkidle，逾時就繼續
                pass
            return page.content()
        except Exception as exc:  # noqa: BLE001
            raise FetchError(f"Playwright 載入失敗：{exc}") from exc
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
