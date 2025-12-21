from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, TypeVar

from ..errors import CLIError

T = TypeVar("T")


def parse_choice(value: str | None, mapping: Mapping[str, T], *, label: str) -> T | None:
    if value is None:
        return None
    key = value.strip().lower()
    if key in mapping:
        return mapping[key]
    choices = ", ".join(sorted(mapping.keys()))
    raise CLIError(
        f"Unknown {label}: {value}",
        error_type="usage_error",
        exit_code=2,
        hint=f"Choose one of: {choices}.",
    )


def parse_iso_datetime(value: str, *, label: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CLIError(
            f"Invalid {label} datetime: {value}",
            error_type="usage_error",
            exit_code=2,
            hint="Use ISO-8601, e.g. 2024-01-01T13:00:00Z or 2024-01-01T13:00:00+00:00.",
        ) from exc


def parse_json_value(value: str, *, label: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise CLIError(
            f"Invalid JSON for {label}.",
            error_type="usage_error",
            exit_code=2,
            hint='Provide a valid JSON literal (e.g. "\\"text\\"", 123, true, {"k": 1}).',
        ) from exc
