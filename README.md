# 通用網頁爬蟲骨架

以 **Python + Playwright + BeautifulSoup** 打造的通用網頁爬蟲。
一個「目標（target）」= 一個網站 / 資料集；核心引擎共用，新目標只要加設定檔。

## 特色

- **雙策略抓取**：靜態頁用 `requests + BeautifulSoup`（快），偵測到需要 JS 渲染才自動切換到 `Playwright`（慢但能處理動態網頁）。
- **中型規模容錯**：斷點續爬（checkpoint）、失敗指數退避重試、隨機延遲速率控制。
- **輸出 Excel**（也支援 CSV / JSON），自動加時間戳檔名、自動調整欄寬。
- **手動 + 排程皆可**：CLI 執行，`run_crawler.bat` 可掛進 Windows 工作排程器，正確回報 exit code。
- **目標模組化**：多數網站只寫 YAML；需要特殊清理才寫少量 Python。

## 環境安裝

```
install_playwright.bat
```

會建立 `.venv`、安裝套件（playwright / pandas / openpyxl / beautifulsoup4 / lxml / requests / PyYAML）並下載 Chromium。

## 執行

```bat
:: 方式一：使用批次檔（自動啟用 venv）
run_crawler.bat example

:: 方式二：手動啟用 venv 後執行
.venv\Scripts\activate
python -m crawler --target example
```

### 常用參數

| 參數 | 說明 |
|---|---|
| `--target <名稱>` | 指定目標（對應 `config/targets/<名稱>.yaml`） |
| `--list-targets` | 列出所有可用目標 |
| `--strategy auto\|static\|dynamic` | 覆寫抓取策略 |
| `--max-pages N` | 本次最多處理幾個列表頁（0 = 不限） |
| `--fresh` | 清除 checkpoint，從頭重新爬 |

範例：

```bat
python -m crawler --target example --max-pages 2
python -m crawler --target example --strategy dynamic
python -m crawler --target example --fresh
```

Exit code：`0` 成功、`1` 設定/執行錯誤、`2` 沒有抓到資料。

## 專案結構

```
web_clawer_setup/
├── install_playwright.bat     環境安裝
├── run_crawler.bat            一鍵執行（給排程器用）
├── requirements.txt
├── crawler/                   核心程式
│   ├── main.py                CLI 進入點
│   ├── engine.py              流程編排（翻頁 / 重試 / checkpoint）
│   ├── fetcher.py             雙策略抓取
│   ├── parser.py              解析與欄位萃取
│   ├── storage.py             輸出（Excel / CSV / JSON）
│   ├── checkpoint.py          斷點續爬
│   └── targets/               目標定義（base + example）
├── config/
│   ├── settings.yaml          全域設定
│   └── targets/example.yaml   範例目標設定
├── data/
│   ├── output/                Excel 產物
│   └── checkpoints/           斷點續爬狀態
└── logs/                      執行 log
```

## 新增一個目標

### 1. 寫設定檔 `config/targets/my_site.yaml`

```yaml
name: my_site
strategy: auto          # auto / static / dynamic
mode: detail            # detail = 列表頁->詳細頁；list = 直接從列表項目萃取
start_url: "https://example.com/list?page=1"

pagination:
  type: url_pattern     # url_pattern / next_link / single
  pattern: "https://example.com/list?page={page}"
  start_page: 1
  max_pages: 3
  # next_link 模式改用：
  # next_selector: "a.next"
  # next_attribute: href

list:
  item_selector: "div.item h3 a"   # detail 模式：抓項目連結
  link_attribute: href
  # list 模式則直接從此元素萃取欄位

fields:
  - name: title
    selector: "h1"
    extract: text                   # text / attribute / html
  - name: price
    selector: "span.price"
    extract: text
    transform: float                # int / float / strip / lower / upper
  - name: link
    selector: "a.detail"
    extract: attribute
    attribute: href
```

### 2. （選用）需要特殊清理時，寫 `crawler/targets/my_site.py`

```python
from crawler.targets.base import BaseTarget, register

@register
class MySiteTarget(BaseTarget):
    name = "my_site"

    def post_process(self, record, base_url):
        record["title"] = (record.get("title") or "").strip()
        return record
```

並在 `crawler/targets/__init__.py` 匯入它。

## 設定 Windows 工作排程器（定期自動執行）

1. 開啟「工作排程器」→「建立基本工作」。
2. 觸發程序選「每天 / 每週」並設定時間。
3. 動作選「啟動程式」：
   - 程式或指令碼：`D:\VIbeCoding\web_clawer_setup\run_crawler.bat`
   - 新增引數：`example`（或你的目標名稱，可加 `--fresh` 等）
   - 開始位置：`D:\VIbeCoding\web_clawer_setup`
4. 完成。之後每次執行結果都會寫入 `logs/`，Excel 輸出在 `data/output/`。

> 若要在背景執行，勾選「無論使用者是否登入都執行」並設定對應帳號權限。

## 合規提醒

- 預設每請求隨機延遲 1~3 秒，請勿調到 0 對目標站造成壓力。
- 請尊重網站的 `robots.txt` 與使用條款，僅爬取允許的內容。
- 自訂 User-Agent 以標示用途。
