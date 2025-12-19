from __future__ import annotations

from affinity.cli.progress import ProgressManager, ProgressSettings


def test_progress_manager_noop_callback_accepts_phase_kwarg() -> None:
    pm = ProgressManager(settings=ProgressSettings(mode="never", quiet=False))
    _, callback = pm.task(description="x", total_bytes=None)
    callback(0, None, phase="download")
