"""通用網頁爬蟲骨架。

核心模組：
- crawler.main     : CLI 進入點
- crawler.engine   : 爬取流程編排（翻頁、重試、checkpoint）
- crawler.fetcher  : 雙策略抓取（靜態 requests 優先，必要時 fallback 到 Playwright）
- crawler.parser   : BeautifulSoup/lxml 解析與欄位萃取
- crawler.storage  : Excel / CSV / JSON 輸出
- crawler.checkpoint: 斷點續爬狀態
- crawler.targets  : 各個目標網站的定義（設定檔 + 選用覆寫）
"""

__version__ = "0.1.0"
