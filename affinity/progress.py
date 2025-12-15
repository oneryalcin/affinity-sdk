"""
Progress callback types used by streaming APIs.

This module is intentionally small and dependency-free so it can be imported by
both services and the HTTP client without creating import cycles.
"""

from __future__ import annotations

from typing import Literal, Protocol

ProgressPhase = Literal["upload", "download"]


class ProgressCallback(Protocol):
    def __call__(
        self,
        bytes_transferred: int,
        total_bytes: int | None,
        *,
        phase: ProgressPhase,
    ) -> None: ...
