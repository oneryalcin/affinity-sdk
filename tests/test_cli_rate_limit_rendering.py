from __future__ import annotations

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")

from affinity.cli.render import RenderSettings, render_result
from affinity.cli.results import CommandContext, CommandMeta, CommandResult
from affinity.models.rate_limit_snapshot import RateLimitSnapshot


def test_rate_limit_footer_is_human_friendly(capsys: pytest.CaptureFixture[str]) -> None:
    snapshot = RateLimitSnapshot(
        api_key_per_minute={"remaining": 898, "limit": 900, "resetSeconds": 9},
        org_monthly={"remaining": 98378, "limit": 100000, "resetSeconds": 1182854},
    )
    result = CommandResult(
        ok=True,
        command=CommandContext(name="version"),
        data={"version": "0.0.0"},
        artifacts=[],
        warnings=[],
        meta=CommandMeta(
            duration_ms=0,
            profile=None,
            resolved=None,
            pagination=None,
            columns=None,
            rate_limit=snapshot,
        ),
        error=None,
    )
    render_result(
        result, settings=RenderSettings(output="table", quiet=False, verbosity=0, pager=False)
    )
    captured = capsys.readouterr()
    assert "Rate limit: user 898/900 reset 0:00:09 | org 98,378/100,000 reset 13d" in captured.out
