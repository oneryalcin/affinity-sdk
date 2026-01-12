from __future__ import annotations

import csv
import io
import logging
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Import to_cell from formatters (single source of truth)
# Re-exported here for backwards compatibility
from .formatters import to_cell

logger = logging.getLogger(__name__)

# Re-export to_cell for any external consumers
__all__ = ["to_cell", "CsvWriteResult", "write_csv", "write_csv_from_rows", "write_csv_to_stdout"]


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


def artifact_path(path: Path) -> tuple[str, bool]:
    """
    Resolve artifact path to relative or absolute string.

    Returns:
        Tuple of (path_string, is_relative)
    """
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
        return str(rel), True
    except Exception:
        return str(path.resolve()), False


def write_csv_from_rows(
    *,
    path: Path,
    rows: Iterable[dict[str, Any]],
    bom: bool = False,
) -> CsvWriteResult:
    """
    Write CSV from row dictionaries with auto-detected columns.

    Detects column names from first row. Handles empty row lists gracefully.

    Args:
        path: Output CSV file path
        rows: Iterable of dictionaries (must all have same keys)
        bom: Whether to write UTF-8 BOM for Excel compatibility

    Returns:
        CsvWriteResult with row/byte counts

    Example:
        >>> rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        >>> write_csv_from_rows(path=Path("out.csv"), rows=rows)
        CsvWriteResult(rows_written=2, bytes_written=42)
    """
    rows_list = list(rows)
    if not rows_list:
        # Write empty file (no headers - we don't know column names without data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return CsvWriteResult(rows_written=0, bytes_written=0)

    fieldnames = list(rows_list[0].keys())

    return write_csv(
        path=path,
        rows=rows_list,
        fieldnames=fieldnames,
        bom=bom,
    )


def write_csv_to_stdout(
    *,
    rows: Iterable[dict[str, Any]],
    fieldnames: list[str],
    bom: bool,
) -> int:
    """
    Write CSV data to stdout.

    Uses TextIOWrapper around stdout.buffer for proper UTF-8 encoding on all platforms.
    BOM is written when bom=True (useful for Excel compatibility when redirecting to file).

    Args:
        rows: Iterable of dictionaries to write
        fieldnames: Column names for CSV header
        bom: Whether to write UTF-8 BOM

    Returns:
        Number of rows written
    """
    encoding = "utf-8-sig" if bom else "utf-8"
    stream = io.TextIOWrapper(sys.stdout.buffer, encoding=encoding, newline="")

    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    rows_written = 0
    for row in rows:
        writer.writerow({k: to_cell(v) for k, v in row.items()})
        rows_written += 1

    stream.flush()
    stream.detach()  # Don't close stdout.buffer
    return rows_written


def localize_iso_string(value: str) -> str:
    """
    Convert ISO datetime string from UTC to local time.

    Used for CSV output where human-readable local time is preferred.

    Args:
        value: ISO datetime string (e.g., "2024-01-01T05:00:00+00:00")

    Returns:
        Local time ISO string (e.g., "2024-01-01T00:00:00-05:00" for EST)
        Returns input unchanged if not a valid datetime string.
    """
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        local = dt.astimezone()
        return local.isoformat()
    except (ValueError, AttributeError):
        # Log at debug level - this is expected for non-datetime fields
        logger.debug("Could not localize value as datetime: %r", value)
        return value  # Return unchanged if not a valid datetime


def localize_row_datetimes(
    row: dict[str, Any],
    datetime_fields: set[str],
) -> dict[str, Any]:
    """
    Localize datetime fields in a row dictionary for CSV output.

    Args:
        row: Dictionary with field values
        datetime_fields: Set of field names that contain datetime values

    Returns:
        New dictionary with datetime fields localized
    """
    result = dict(row)
    for field in datetime_fields:
        if field in result and isinstance(result[field], str):
            result[field] = localize_iso_string(result[field])
    return result
