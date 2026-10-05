"""CLI 進入點。

範例：
    python -m crawler --target example
    python -m crawler --target example --max-pages 2
    python -m crawler --target example --strategy dynamic
    python -m crawler --target example --fresh
    python -m crawler --list-targets
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

# 確保直接執行時也能匯入 crawler 套件
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import (  # noqa: E402
    PROJECT_ROOT,
    list_targets,
    load_settings,
    load_target_config,
)
from crawler.engine import CrawlerEngine  # noqa: E402
from crawler.fetcher import Fetcher  # noqa: E402
from crawler.targets import BaseTarget, registered  # noqa: E402
import crawler.targets  # noqa: E402,F401  （確保所有目標模組被匯入、完成註冊）


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawler", description="通用網頁爬蟲（Playwright + BeautifulSoup）"
    )
    parser.add_argument("--target", help="目標名稱（對應 config/targets/<name>.yaml）")
    parser.add_argument("--list-targets", action="store_true", help="列出所有可用目標後結束")
    parser.add_argument(
        "--strategy",
        choices=["auto", "static", "dynamic"],
        help="覆寫抓取策略（預設讀取設定檔）",
    )
    parser.add_argument("--max-pages", type=int, help="本次最多處理幾個列表頁（0=不限）")
    parser.add_argument("--fresh", action="store_true", help="清除 checkpoint，從頭重新爬")
    parser.add_argument("--config-dir", help="設定檔目錄（預設：專案下的 config/）")
    parser.add_argument("--log-level", help="log 等級（DEBUG/INFO/WARNING/ERROR）")
    return parser


def setup_logging(log_dir: Path, level: str, target_name: str) -> logging.Logger:
    import datetime

    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = log_dir / f"crawl_{target_name}_{timestamp}.log"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers.append(logging.FileHandler(logfile, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logger = logging.getLogger("crawler")
    logger.info("log 檔：%s", logfile)
    return logger


def build_target(
    name: str,
    config_dir: Path,
    settings: dict[str, Any],
    fetcher: Fetcher,
    logger: logging.Logger,
) -> BaseTarget:
    config = load_target_config(name, config_dir)
    target_cls = registered(name) or BaseTarget
    if target_cls is not BaseTarget:
        logger.info("使用目標類別：%s", target_cls.__name__)
    return target_cls(config, settings, fetcher, logger)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_dir = Path(args.config_dir) if args.config_dir else None

    if args.list_targets:
        targets = list_targets(config_dir)
        if targets:
            print("可用目標：")
            for name in targets:
                print(f"  - {name}")
        else:
            print("目前沒有任何目標設定（config/targets/*.yaml）")
        return 0

    if not args.target:
        build_parser().print_help()
        print("\n錯誤：請指定 --target 或使用 --list-targets", file=sys.stderr)
        return 1

    try:
        settings = load_settings(config_dir)
    except FileNotFoundError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    # CLI 覆寫設定
    if args.strategy:
        settings.setdefault("fetch", {})["strategy"] = args.strategy
    if args.max_pages is not None:
        settings.setdefault("run", {})["max_pages"] = args.max_pages
    if args.log_level:
        settings.setdefault("logging", {})["level"] = args.log_level

    log_dir = Path(settings["logging"].get("dir", "logs"))
    if not log_dir.is_absolute():
        log_dir = PROJECT_ROOT / log_dir
    logger = setup_logging(log_dir, settings["logging"].get("level", "INFO"), args.target)

    fetcher = Fetcher(settings.get("fetch", {}), settings.get("browser", {}), logger)
    try:
        target = build_target(args.target, config_dir, settings, fetcher, logger)
        engine = CrawlerEngine(target, fetcher, settings, logger, PROJECT_ROOT)
        path = engine.run(fresh=args.fresh)
    except FileNotFoundError as exc:
        logger.error("設定錯誤：%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("執行失敗：%s", exc)
        return 1
    finally:
        fetcher.close()

    if path is None:
        logger.warning("本次沒有產生輸出檔")
        return 2
    print(f"\n完成！輸出檔：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
