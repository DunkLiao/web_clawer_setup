"""讓 `python -m crawler` 可以執行。"""
from crawler.main import main

if __name__ == "__main__":
    raise SystemExit(main())
