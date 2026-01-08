from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from affinity.progress import ProgressCallback, ProgressPhase

logger = logging.getLogger(__name__)

ProgressMode = Literal["auto", "always", "never"]


@dataclass(frozen=True, slots=True)
class ProgressSettings:
    mode: ProgressMode
    quiet: bool


class ProgressManager(AbstractContextManager["ProgressManager"]):
    # Rate limit to stay under mcp-bash 100/min limit
    # Using 0.65s (not 0.6s) to leave headroom for timing jitter (~92/min max)
    _MIN_PROGRESS_INTERVAL = 0.65

    def __init__(self, *, settings: ProgressSettings):
        self._settings = settings
        self._console = Console(file=sys.stderr)
        self._progress: Progress | None = None
        # JSON mode: emit NDJSON to stderr when not a TTY (for MCP consumption)
        self._json_mode = (
            settings.mode != "never" and not settings.quiet and not sys.stderr.isatty()
        )
        if self._json_mode:
            logger.debug("Progress JSON mode enabled (stderr is not a TTY)")
        # Use -inf so first call always succeeds regardless of time.monotonic() value
        self._last_progress_time: float = float("-inf")
        self._emitted_100: bool = False
        self._current_task_description: str = ""

    def __enter__(self) -> ProgressManager:
        if self.enabled:
            self._progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=self._console,
                transient=True,
            )
            self._progress.__enter__()
        return self

    def _emit_json_progress(
        self,
        percent: int | None,
        message: str,
        current: int | None = None,
        total: int | None = None,
        *,
        force: bool = False,
    ) -> None:
        """Emit NDJSON progress to stderr for MCP consumption.

        Args:
            percent: Progress percentage (0-100), or None for indeterminate progress.
            message: Human-readable progress message.
            current: Current value (e.g., bytes transferred).
            total: Total value (e.g., total bytes).
            force: Bypass rate limiting (for completion messages).
        """
        # Rate limit to avoid overwhelming MCP client (unless forced)
        now = time.monotonic()
        if not force and now - self._last_progress_time < self._MIN_PROGRESS_INTERVAL:
            return
        self._last_progress_time = now

        # Include "type": "progress" to distinguish from error JSON on stderr
        obj: dict[str, int | str | None] = {
            "type": "progress",
            "progress": percent,
            "message": message,
        }
        if current is not None:
            obj["current"] = current
        if total is not None:
            obj["total"] = total
        # flush=True is CRITICAL: Python buffers stderr when not a TTY,
        # so without flush, lines may not appear until buffer fills or process exits
        print(json.dumps(obj), file=sys.stderr, flush=True)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Emit guaranteed 100% completion for JSON mode (bypass rate limiting)
        if self._json_mode and not self._emitted_100 and exc_type is None:
            self._emit_json_progress(100, f"{self._current_task_description} complete", force=True)
            self._emitted_100 = True
        # Existing Rich cleanup
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc, tb)
        self._progress = None

    @property
    def enabled(self) -> bool:
        if self._settings.quiet:
            return False
        if self._settings.mode == "never":
            return False
        if self._settings.mode == "always":
            return True
        return sys.stderr.isatty()

    def task(self, *, description: str, total_bytes: int | None) -> tuple[TaskID, ProgressCallback]:
        # Track description for __exit__ 100% emission
        self._current_task_description = description
        self._emitted_100 = False

        # JSON mode callback (when stderr is not a TTY)
        if self._json_mode:

            def json_callback(
                bytes_transferred: int, total_bytes_arg: int | None, *, phase: ProgressPhase
            ) -> None:
                del phase
                # Compute percent from bytes (None total = indeterminate progress)
                percent = bytes_transferred * 100 // total_bytes_arg if total_bytes_arg else None
                self._emit_json_progress(percent, description, bytes_transferred, total_bytes_arg)
                # Track if we've hit 100% (only for determinate progress)
                if percent is not None and percent >= 100:
                    self._emitted_100 = True

            # TaskID(0) is a no-op sentinel (progress not tracked in Rich)
            return TaskID(0), cast(ProgressCallback, json_callback)

        # Existing Rich progress bar logic
        if not self.enabled or self._progress is None:

            def noop(_: int, __: int | None, *, phase: ProgressPhase) -> None:
                del phase

            return TaskID(0), cast(ProgressCallback, noop)

        task_id = self._progress.add_task(description, total=total_bytes)

        def callback(bytes_transferred: int, total: int | None, *, phase: ProgressPhase) -> None:
            del phase
            if self._progress is None:
                return
            if total is not None:
                self._progress.update(task_id, total=total)
            self._progress.update(task_id, completed=bytes_transferred)

        return task_id, cast(ProgressCallback, callback)

    def advance(self, task_id: TaskID, advance: int = 1) -> None:
        if self._progress is None:
            return
        self._progress.advance(task_id, advance)

    def simple_status(self, text: str) -> None:
        if not self.enabled:
            return
        self._console.print(text)
