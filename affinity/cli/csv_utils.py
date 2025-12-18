from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CsvWriteResult:
    rows_written: int
    bytes_written: int


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, *, max_len: int = 180) -> str:
    cleaned = _FILENAME_SAFE.sub("_", name).strip("._- ")
    if not cleaned:
        cleaned = "file"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def to_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(to_cell(v) for v in value if v is not None)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def write_csv(
    *,
    path: Path,
    rows: Iterable[dict[str, Any]],
    fieldnames: list[str],
    bom: bool,
) -> CsvWriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if bom else "utf-8"
    rows_written = 0

    with path.open("w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: to_cell(v) for k, v in row.items()})
            rows_written += 1

    bytes_written = path.stat().st_size
    return CsvWriteResult(rows_written=rows_written, bytes_written=bytes_written)
