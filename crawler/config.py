"""設定檔載入與預設值合併。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# 專案根目錄（crawler/ 的上一層）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"

# 程式碼內建預設值；settings.yaml 缺少的欄位會自動補上
DEFAULT_SETTINGS: dict[str, Any] = {
    "fetch": {
        "strategy": "auto",
        "delay_min": 1.0,
        "delay_max": 3.0,
        "timeout": 30,
        "retries": 3,
        "retry_backoff": [5, 15, 45],
        "user_agent": "Mozilla/5.0 (compatible; WebCrawlerSetup/0.1)",
        "respect_robots": True,
    },
    "browser": {
        "headless": True,
    },
    "run": {
        "max_pages": 0,
        "stop_on_error": False,
    },
    "output": {
        "dir": "data/output",
        "format": "xlsx",
        "add_timestamp": True,
    },
    "checkpoint": {
        "enabled": True,
        "dir": "data/checkpoints",
    },
    "logging": {
        "dir": "logs",
        "level": "INFO",
    },
}


def read_yaml(path: Path) -> dict[str, Any]:
    """讀取 YAML 檔；空檔回傳空 dict。"""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"設定檔格式錯誤（最外層應為 key: value）：{path}")
    return data


def deep_merge(base: dict, override: dict) -> dict:
    """遞迴合併兩個 dict（override 優先），回傳新 dict。"""
    result = dict(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(config_dir: Path | str | None = None) -> dict[str, Any]:
    """載入全域設定並補上預設值。"""
    config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    path = config_dir / "settings.yaml"
    if not path.exists():
        raise FileNotFoundError(f"找不到全域設定檔：{path}")
    user_settings = read_yaml(path)
    return deep_merge(DEFAULT_SETTINGS, user_settings)


def load_target_config(
    name: str, config_dir: Path | str | None = None
) -> dict[str, Any]:
    """載入單一目標設定檔 config/targets/<name>.yaml。"""
    config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    path = config_dir / "targets" / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"找不到目標設定檔：{path}")
    config = read_yaml(path)
    config.setdefault("name", name)
    config.setdefault("mode", "detail")
    config.setdefault("fields", [])
    return config


def list_targets(config_dir: Path | str | None = None) -> list[str]:
    """列出所有可用的目標名稱。"""
    config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    targets_dir = config_dir / "targets"
    if not targets_dir.exists():
        return []
    return sorted(p.stem for p in targets_dir.glob("*.yaml"))
