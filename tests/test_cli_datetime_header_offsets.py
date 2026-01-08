from __future__ import annotations

import io
import os
import time
from datetime import datetime, timezone

import pytest
from rich.console import Console

from affinity.cli.render import _table_from_rows


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset not available on this platform")
def test_table_from_rows_marks_offset_varies_when_dst_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    try:
        time.tzset()  # type: ignore[attr-defined]
    except Exception:
        pytest.skip("timezone database not available for America/Los_Angeles")

    try:
        table, _ = _table_from_rows(
            [
                {
                    "id": 1,
                    "t": datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 2,
                    "t": datetime(2020, 7, 1, 12, 0, tzinfo=timezone.utc),
                },
            ]
        )

        console = Console(file=io.StringIO(), force_terminal=True, width=200)
        rendered = "\n".join(
            str(line) for line in console.render_lines(table, options=console.options)
        )
        assert "t (local)" in rendered
        assert "UTC-" not in rendered
    finally:
        if old_tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", old_tz)
        time.tzset()  # type: ignore[attr-defined]
