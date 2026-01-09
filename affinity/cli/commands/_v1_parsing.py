from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
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
    """
    Parse ISO-8601 datetime string to UTC-aware datetime.

    Timezone handling:
    - Explicit timezone (Z or offset): Respected, converted to UTC
    - Naive string: Interpreted as LOCAL time, converted to UTC

    This provides intuitive UX for CLI users who think in local time.

    Examples (assuming user is in EST/UTC-5):
        "2024-01-01"            → 2024-01-01T05:00:00Z (midnight EST)
        "2024-01-01T12:00:00"   → 2024-01-01T17:00:00Z (noon EST)
        "2024-01-01T12:00:00Z"  → 2024-01-01T12:00:00Z (explicit UTC)
        "2024-01-01T12:00:00-05:00" → 2024-01-01T17:00:00Z (explicit EST)

    Returns:
        UTC-aware datetime object
    """
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CLIError(
            f"Invalid {label} datetime: {value}",
            error_type="usage_error",
            exit_code=2,
            hint="Use ISO-8601, e.g. 2024-01-01, 2024-01-01T13:00:00, or 2024-01-01T13:00:00Z.",
        ) from exc

    # Convert to UTC
    if dt.tzinfo is None:
        # Naive datetime = local time
        # astimezone() on naive datetime uses system timezone
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


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
