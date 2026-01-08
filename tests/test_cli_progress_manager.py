from __future__ import annotations

import json
import sys

import pytest

from affinity.cli.progress import ProgressManager, ProgressSettings


def test_progress_manager_noop_callback_accepts_phase_kwarg() -> None:
    pm = ProgressManager(settings=ProgressSettings(mode="never", quiet=False))
    _, callback = pm.task(description="x", total_bytes=None)
    callback(0, None, phase="download")


def test_progress_json_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify TTY detection outputs NDJSON to stderr."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)

    settings = ProgressSettings(mode="auto", quiet=False)
    with ProgressManager(settings=settings) as pm:
        _, cb = pm.task(description="Uploading test.pdf", total_bytes=100)
        cb(50, 100, phase="upload")

    captured = capsys.readouterr()
    lines = [line for line in captured.err.strip().split("\n") if line]
    # Should have at least one progress line (50%) and possibly 100% from __exit__
    assert len(lines) >= 1
    line = json.loads(lines[0])
    assert line["type"] == "progress"
    assert line["progress"] == 50
    assert line["message"] == "Uploading test.pdf"
    assert line["current"] == 50
    assert line["total"] == 100


def test_progress_rate_limiting(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify rate limiting skips rapid updates."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)

    # Mock time.monotonic() to control rate limiting
    # NOTE: Must patch in the module where it's used, not globally
    # Need 4 values: 3 for callbacks + 1 for __exit__ forced call
    time_values = iter([0.0, 0.1, 0.8, 1.0])
    monkeypatch.setattr("affinity.cli.progress.time.monotonic", lambda: next(time_values))

    settings = ProgressSettings(mode="auto", quiet=False)
    with ProgressManager(settings=settings) as pm:
        _, cb = pm.task(description="test", total_bytes=100)

        # First call (t=0.0) should emit
        cb(10, 100, phase="upload")
        # Second call (t=0.1) should be skipped (only 0.1s elapsed < 0.65s interval)
        cb(20, 100, phase="upload")
        # Third call (t=0.8) should emit (0.8s > 0.65s interval from first)
        cb(30, 100, phase="upload")

    captured = capsys.readouterr()
    # Filter to only progress lines (exclude 100% from __exit__ which has different timing)
    lines = [
        json.loads(line)
        for line in captured.err.strip().split("\n")
        if line and json.loads(line).get("progress") not in (None, 100)
    ]
    assert len(lines) == 2  # First (10%) and third (30%) emitted, second (20%) skipped
    assert lines[0]["progress"] == 10
    assert lines[1]["progress"] == 30


def test_progress_tty_mode_preserves_rich_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: TTY mode should NOT emit JSON (preserve Rich bars)."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    settings = ProgressSettings(mode="auto", quiet=False)
    pm = ProgressManager(settings=settings)

    # Should NOT be in JSON mode when TTY
    assert not pm._json_mode


def test_progress_indeterminate(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify indeterminate progress (no total) emits progress: null."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)

    settings = ProgressSettings(mode="auto", quiet=False)
    with ProgressManager(settings=settings) as pm:
        _, cb = pm.task(description="Searching", total_bytes=None)
        cb(100, None, phase="download")

    captured = capsys.readouterr()
    lines = [line for line in captured.err.strip().split("\n") if line]
    line = json.loads(lines[0])
    assert line["type"] == "progress"
    assert line["progress"] is None  # Indeterminate
    assert line["current"] == 100
    assert "total" not in line or line["total"] is None


def test_progress_force_bypasses_rate_limit(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify force=True always emits regardless of timing."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    # All calls at t=0, so normally rate limited
    monkeypatch.setattr("affinity.cli.progress.time.monotonic", lambda: 0.0)

    settings = ProgressSettings(mode="auto", quiet=False)
    pm = ProgressManager(settings=settings)
    pm.__enter__()
    pm._current_task_description = "Testing"

    # First emission (always succeeds)
    pm._emit_json_progress(10, "Working")
    # Second emission at same time without force (should be skipped)
    pm._emit_json_progress(20, "Still working")
    # Third emission with force=True (should succeed despite rate limit)
    pm._emit_json_progress(100, "Complete", force=True)

    captured = capsys.readouterr()
    lines = [line for line in captured.err.strip().split("\n") if line]
    assert len(lines) == 2  # First and forced third, second skipped
    assert json.loads(lines[0])["progress"] == 10
    assert json.loads(lines[1])["progress"] == 100


def test_progress_100_completion_forced(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify 100% is emitted on context manager exit even if rate-limited."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    # All calls at t=0, so rate limited
    monkeypatch.setattr("affinity.cli.progress.time.monotonic", lambda: 0.0)

    settings = ProgressSettings(mode="auto", quiet=False)
    with ProgressManager(settings=settings) as pm:
        _, cb = pm.task(description="Uploading", total_bytes=100)
        cb(50, 100, phase="upload")  # Emits (first call)
        cb(75, 100, phase="upload")  # Skipped (rate limited)
        # NOT calling cb(100, ...) - context manager should emit it

    captured = capsys.readouterr()
    lines = [line for line in captured.err.strip().split("\n") if line]
    # Should have 2 lines: first update + forced 100% from __exit__
    assert len(lines) == 2
    last = json.loads(lines[-1])
    assert last["progress"] == 100
    assert "complete" in last["message"].lower()


def test_progress_json_callback_accepts_phase_kwarg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify JSON callback accepts phase keyword argument like noop callback."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)

    pm = ProgressManager(settings=ProgressSettings(mode="auto", quiet=False))
    _, callback = pm.task(description="x", total_bytes=100)
    # Should not raise
    callback(50, 100, phase="download")
