from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, TypeVar

from ..errors import CLIError
from ..query.dates import is_relative_date, parse_relative_date

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


def validate_domain(value: str | None, *, label: str = "domain") -> str | None:
    """
    Validate domain format before API call.

    Checks for common domain format mistakes that would be rejected by the
    Affinity API with a cryptic error message. Validates against RFC 1035
    constraints and common user errors.

    Args:
        value: Domain string to validate (or None)
        label: Human-readable label for error messages

    Returns:
        The validated domain string (unchanged), or None if input was None

    Raises:
        CLIError: If domain format is invalid
    """
    if value is None:
        return None

    domain = value.strip()
    if not domain:
        return None

    # Check for protocol prefix (common mistake)
    if domain.startswith(("http://", "https://")):
        # Extract domain from URL
        clean = domain.split("//", 1)[1].split("/", 1)[0]
        raise CLIError(
            f"Invalid {label}: provide domain only, not URL",
            error_type="usage_error",
            exit_code=2,
            hint=f"Use '{clean}' instead of '{value}'.",
        )

    # Check for underscores (RFC 1035 violation - most common issue)
    if "_" in domain:
        suggested = domain.replace("_", "-")
        raise CLIError(
            f"Invalid {label}: domains cannot contain underscores",
            error_type="usage_error",
            exit_code=2,
            hint=f"Use '{suggested}' instead of '{domain}'.",
        )

    # Check for spaces
    if " " in domain:
        raise CLIError(
            f"Invalid {label}: domains cannot contain spaces",
            error_type="usage_error",
            exit_code=2,
            hint="Remove spaces from the domain.",
        )

    return domain


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


def parse_date_flexible(
    value: str,
    *,
    label: str,
    now: datetime | None = None,
) -> datetime:
    """
    Parse date string as either relative or ISO format.

    Tries relative first (+7d, tomorrow), then ISO-8601.
    Returns UTC-aware datetime.

    Args:
        value: Date string to parse
        label: Human-readable label for error messages
        now: Reference time for relative dates (default: current UTC)

    Returns:
        UTC-aware datetime

    Raises:
        CLIError: If value cannot be parsed as either format
    """
    # Validate non-empty
    if not value or not value.strip():
        raise CLIError(
            f"Missing {label} date value",
            error_type="usage_error",
            exit_code=2,
        )

    # Try relative date first
    if is_relative_date(value):
        try:
            return parse_relative_date(value, now=now, use_utc=True)
        except ValueError:
            pass  # Shouldn't happen if is_relative_date() returned True

    # Fall back to ISO parsing, but wrap error with unified hint
    try:
        return parse_iso_datetime(value, label=label)
    except CLIError:
        raise CLIError(
            f"Invalid {label} date: {value}",
            error_type="usage_error",
            exit_code=2,
            hint="Use ISO-8601 (2026-01-01), relative (+7d, +2w), or keyword (today, tomorrow).",
        ) from None


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
