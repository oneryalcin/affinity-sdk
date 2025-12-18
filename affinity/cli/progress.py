from __future__ import annotations

import sys
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

ProgressMode = Literal["auto", "always", "never"]


@dataclass(frozen=True, slots=True)
class ProgressSettings:
    mode: ProgressMode
    quiet: bool


class ProgressManager(AbstractContextManager["ProgressManager"]):
    def __init__(self, *, settings: ProgressSettings):
        self._settings = settings
        self._console = Console(file=sys.stderr)
        self._progress: Progress | None = None

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

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
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
        if not self.enabled or self._progress is None:

            def noop(_: int, __: int | None, *, _phase: ProgressPhase) -> None:
                return

            return TaskID(0), cast(ProgressCallback, noop)

        task_id = self._progress.add_task(description, total=total_bytes)

        def callback(bytes_transferred: int, total: int | None, *, _phase: ProgressPhase) -> None:
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
