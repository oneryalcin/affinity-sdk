"""Progress display for query execution.

Provides Rich progress bars for TTY and NDJSON progress for non-TTY (MCP).
This module is CLI-only and NOT part of the public SDK API.
"""

from __future__ import annotations

import json
import sys
import time
from typing import TYPE_CHECKING, Any, TextIO

from .executor import QueryProgressCallback
from .models import PlanStep

if TYPE_CHECKING:
    from rich.console import Console
    from rich.progress import TaskID


# =============================================================================
# Rich Progress Display (TTY)
# =============================================================================


class RichQueryProgress(QueryProgressCallback):  # pragma: no cover
    """Rich progress display for terminal output.

    Shows multi-step progress with:
    - Overall progress bar
    - Per-step progress bars
    - Step descriptions and status
    """

    def __init__(
        self,
        console: Console | None = None,
        total_steps: int = 1,
    ) -> None:
        """Initialize Rich progress display.

        Args:
            console: Rich console (defaults to stderr)
            total_steps: Total number of steps in plan
        """
        from rich.console import Console
        from rich.progress import (
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        self.console = console or Console(stderr=True)
        self.total_steps = total_steps
        self.completed_steps = 0

        # Simple progress: spinner + description + elapsed time
        # No percentage/bar since total records are unknown for most operations
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )

        self._overall_task: TaskID | None = None
        self._step_tasks: dict[int, TaskID] = {}
        self._started = False

    def __enter__(self) -> RichQueryProgress:
        """Start progress display."""
        self.progress.start()
        self._started = True
        self._overall_task = self.progress.add_task(
            "[bold]Overall Progress",
            total=self.total_steps,
        )
        return self

    def __exit__(self, *args: object) -> None:
        """Stop progress display."""
        self.progress.stop()
        self._started = False

    def on_step_start(self, step: PlanStep) -> None:
        """Called when a step starts."""
        if not self._started:
            return

        task_id = self.progress.add_task(
            f"[cyan]{step.description}",
            total=None,  # Indeterminate
        )
        self._step_tasks[step.step_id] = task_id

    def on_step_progress(self, step: PlanStep, current: int, total: int | None) -> None:
        """Called during step execution."""
        if not self._started:
            return

        task_id = self._step_tasks.get(step.step_id)
        if task_id is not None:
            if total is not None:
                self.progress.update(task_id, completed=current, total=total)
            else:
                # No total known - show record count in description instead
                self.progress.update(
                    task_id,
                    completed=current,
                    description=f"[cyan]{step.description} ({current:,} records)",
                )

    def on_step_complete(self, step: PlanStep, records: int) -> None:
        """Called when a step completes."""
        if not self._started:
            return

        task_id = self._step_tasks.get(step.step_id)
        if task_id is not None:
            self.progress.update(
                task_id,
                completed=100,
                total=100,
                description=f"[green]✓ {step.description} ({records} records)",
            )

        self.completed_steps += 1
        if self._overall_task is not None:
            self.progress.update(self._overall_task, completed=self.completed_steps)

    def on_step_error(self, step: PlanStep, error: Exception) -> None:
        """Called when a step fails."""
        if not self._started:
            return

        task_id = self._step_tasks.get(step.step_id)
        if task_id is not None:
            self.progress.update(
                task_id,
                description=f"[red]✗ {step.description}: {error}",
            )


# =============================================================================
# NDJSON Progress (Non-TTY / MCP)
# =============================================================================


class NDJSONQueryProgress(QueryProgressCallback):
    """NDJSON progress output for non-TTY environments.

    Emits progress updates as newline-delimited JSON for:
    - MCP tool integration
    - Scripting and automation
    """

    MIN_PROGRESS_INTERVAL = 0.65  # Minimum seconds between progress updates

    def __init__(self, output: TextIO | None = None) -> None:
        """Initialize NDJSON progress.

        Args:
            output: Output stream (defaults to stderr)
        """
        self.output = output or sys.stderr
        self._last_emit: dict[int, float] = {}

    def _emit(self, data: dict[str, Any], *, force: bool = False) -> None:
        """Emit a progress JSON object."""
        step_id = data.get("stepId", -1)
        now = time.time()

        # Rate limit per step
        if not force:
            last = self._last_emit.get(step_id, 0)
            if now - last < self.MIN_PROGRESS_INTERVAL:
                return

        self._last_emit[step_id] = now
        self.output.write(json.dumps(data) + "\n")
        self.output.flush()

    def on_step_start(self, step: PlanStep) -> None:
        """Called when a step starts."""
        self._emit(
            {
                "type": "progress",
                "event": "step_start",
                "stepId": step.step_id,
                "operation": step.operation,
                "description": step.description,
            }
        )

    def on_step_progress(self, step: PlanStep, current: int, total: int | None) -> None:
        """Called during step execution."""
        progress = None
        if total is not None and total > 0:
            progress = round((current / total) * 100)

        self._emit(
            {
                "type": "progress",
                "event": "step_progress",
                "stepId": step.step_id,
                "current": current,
                "total": total,
                "progress": progress,
            }
        )

    def on_step_complete(self, step: PlanStep, records: int) -> None:
        """Called when a step completes."""
        self._emit(
            {
                "type": "progress",
                "event": "step_complete",
                "stepId": step.step_id,
                "records": records,
                "progress": 100,
            },
            force=True,
        )

    def on_step_error(self, step: PlanStep, error: Exception) -> None:
        """Called when a step fails."""
        self._emit(
            {
                "type": "progress",
                "event": "step_error",
                "stepId": step.step_id,
                "error": str(error),
            },
            force=True,
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_progress_callback(  # pragma: no cover
    *,
    total_steps: int = 1,
    quiet: bool = False,
    force_ndjson: bool = False,
) -> QueryProgressCallback:
    """Create appropriate progress callback based on environment.

    Args:
        total_steps: Total number of steps in plan
        quiet: If True, return null callback
        force_ndjson: If True, use NDJSON even on TTY

    Returns:
        Appropriate progress callback
    """
    from .executor import NullProgressCallback

    if quiet:
        return NullProgressCallback()

    if force_ndjson or not sys.stderr.isatty():
        return NDJSONQueryProgress()

    return RichQueryProgress(total_steps=total_steps)
