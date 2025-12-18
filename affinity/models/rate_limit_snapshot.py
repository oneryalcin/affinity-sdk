"""
Unified, version-agnostic rate limit snapshot models.

These models represent the SDK's stable public surface for inspecting rate limit
state, independent of whether the underlying request used v1 or v2 endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .entities import AffinityModel

RateLimitSource = Literal["headers", "endpoint", "unknown"]


class RateLimitBucket(AffinityModel):
    """A single rate limit bucket (quota window)."""

    limit: int | None = None
    remaining: int | None = None
    reset_seconds: int | None = Field(None, alias="resetSeconds")
    used: int | None = None


class RateLimitSnapshot(AffinityModel):
    """
    A best-effort snapshot of rate limit state.

    Notes:
    - `source="headers"` means the snapshot is derived from tracked HTTP response headers.
    - `source="endpoint"` means the snapshot is derived from a dedicated endpoint response payload.
    - `source="unknown"` means no reliable rate limit information has been observed yet.
    """

    api_key_per_minute: RateLimitBucket = Field(
        default_factory=RateLimitBucket, alias="apiKeyPerMinute"
    )
    org_monthly: RateLimitBucket = Field(default_factory=RateLimitBucket, alias="orgMonthly")
    concurrent: RateLimitBucket | None = None

    observed_at: datetime | None = Field(None, alias="observedAt")
    age_seconds: float | None = Field(None, alias="ageSeconds")
    source: RateLimitSource = "unknown"
    request_id: str | None = Field(None, alias="requestId")
