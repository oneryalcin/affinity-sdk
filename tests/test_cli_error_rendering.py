from __future__ import annotations

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")

from click.testing import CliRunner

from affinity.cli.main import cli
from affinity.cli.render import RenderSettings, render_result
from affinity.cli.results import CommandMeta, CommandResult, ErrorInfo


def test_resolve_url_parsed_before_api_key_required() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["resolve-url", "not-a-url"], env={"AFFINITY_API_KEY": ""})
    assert result.exit_code == 2
    assert "URL must start with http:// or https://" in result.output


def test_missing_api_key_error_does_not_print_help_hint() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["whoami"], env={"AFFINITY_API_KEY": ""})
    assert result.exit_code == 2
    assert "Missing API key." in result.output
    assert "Hint: run `affinity whoami --help`" not in result.output


def test_ambiguous_resolution_renders_match_table(capsys: pytest.CaptureFixture[str]) -> None:
    result = CommandResult(
        ok=False,
        command="list export",
        data=None,
        artifacts=[],
        warnings=[],
        meta=CommandMeta(duration_ms=0, profile=None, resolved=None, pagination=None, columns=None),
        error=ErrorInfo(
            type="ambiguous_resolution",
            message='Ambiguous list name: "Pipeline" (2 matches)',
            details={
                "selector": "Pipeline",
                "matches": [
                    {"listId": 1, "name": "Pipeline", "type": "opportunity"},
                    {"listId": 2, "name": "Pipeline", "type": "opportunity"},
                ],
            },
        ),
    )
    render_result(
        result,
        settings=RenderSettings(output="table", quiet=False, verbosity=0, pager=False),
    )
    captured = capsys.readouterr()
    assert "Ambiguous:" in captured.err
    assert "listId" in captured.err
    assert "Pipeline" in captured.err
