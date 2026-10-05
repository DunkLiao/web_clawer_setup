"""資料輸出層：Excel（預設）/ CSV / JSON。"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd


class Storage:
    def __init__(self, out_dir: Path | str, fmt: str = "xlsx", add_timestamp: bool = True):
        self.dir = Path(out_dir)
        self.fmt = (fmt or "xlsx").lower()
        self.add_timestamp = add_timestamp

    def save(self, records: list[dict[str, Any]], target_name: str) -> Path:
        if not records:
            raise ValueError("沒有可輸出的資料")

        self.dir.mkdir(parents=True, exist_ok=True)
        stem = f"crawl_{target_name}"
        if self.add_timestamp:
            stem += "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.fmt == "xlsx":
            path = self.dir / f"{stem}.xlsx"
            self._write_excel(pd.DataFrame(records), path)
        elif self.fmt == "csv":
            path = self.dir / f"{stem}.csv"
            pd.DataFrame(records).to_csv(path, index=False, encoding="utf-8-sig")
        elif self.fmt == "json":
            path = self.dir / f"{stem}.json"
            path.write_text(
                json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            raise ValueError(f"不支援的輸出格式：{self.fmt}")

        return path

    @staticmethod
    def _write_excel(df: pd.DataFrame, path: Path) -> None:
        from openpyxl.utils import get_column_letter

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="data")
            worksheet = writer.sheets["data"]
            for idx, column in enumerate(df.columns, start=1):
                try:
                    values = [str(column)] + [str(v) for v in df[column].head(300)]
                    width = max(len(v) for v in values) + 2
                except Exception:  # noqa: BLE001
                    width = len(str(column)) + 2
                worksheet.column_dimensions[get_column_letter(idx)].width = min(max(10, width), 60)
