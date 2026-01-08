from __future__ import annotations

import io
import os
import time
from datetime import datetime, timezone

import pytest
from rich.console import Console

from affinity.cli.render import _table_from_rows


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset not available on this platform")
def test_table_from_rows_formats_datetimes_in_local_time(monkeypatch: pytest.MonkeyPatch) -> None:
    old_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()  # type: ignore[attr-defined]

    try:
        table, _ = _table_from_rows(
            [
                {
                    "id": 1,
                    "lastInteractionDate": datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc),
                }
            ]
        )
        console = Console(file=io.StringIO(), force_terminal=True, width=200)
        rendered = "\n".join(
            str(line) for line in console.render_lines(table, options=console.options)
        )
        assert "lastInteractionDate (local, UTC+0)" in rendered
        assert "2025-01-02 03:04" in rendered
    finally:
        if old_tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", old_tz)
        time.tzset()  # type: ignore[attr-defined]
