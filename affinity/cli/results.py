from __future__ import annotations

from typing import Any

from pydantic import Field

from affinity.models.entities import AffinityModel
from affinity.models.rate_limit_snapshot import RateLimitSnapshot


class Artifact(AffinityModel):
    type: str
    path: str
    path_is_relative: bool = Field(..., alias="pathIsRelative")
    rows_written: int | None = Field(None, alias="rowsWritten")
    bytes_written: int | None = Field(None, alias="bytesWritten")
    partial: bool = False


class ErrorInfo(AffinityModel):
    type: str
    message: str
    hint: str | None = None
    docs_url: str | None = Field(None, alias="docsUrl")
    details: dict[str, Any] | None = None


class CommandMeta(AffinityModel):
    duration_ms: int = Field(..., alias="durationMs")
    profile: str | None = None
    resolved: dict[str, Any] | None = None
    pagination: dict[str, Any] | None = None
    columns: list[dict[str, Any]] | None = None
    rate_limit: RateLimitSnapshot | None = Field(None, alias="rateLimit")


class CommandResult(AffinityModel):
    ok: bool
    command: str
    data: Any | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    meta: CommandMeta
    error: ErrorInfo | None = None
