from __future__ import annotations

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")

from click.testing import CliRunner

from affinity.cli.config import LoadedConfig, ProfileConfig
from affinity.cli.context import error_info_for_exception, normalize_exception
from affinity.cli.main import cli
from affinity.cli.render import RenderSettings, render_result
from affinity.cli.results import CommandContext, CommandMeta, CommandResult, ErrorInfo
from affinity.exceptions import ErrorDiagnostics, ValidationError


def test_resolve_url_parsed_before_api_key_required() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["resolve-url", "not-a-url"], env={"AFFINITY_API_KEY": ""})
    assert result.exit_code == 2
    assert "URL must start with http:// or https://" in result.output


def test_missing_api_key_error_does_not_print_help_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that missing API key error doesn't include unhelpful --help hint.

    Mocks load_config to return empty config, preventing fallback to real config file.
    """
    # Return empty config with no API key
    empty_config = LoadedConfig(default=ProfileConfig(), profiles={})
    # Must patch in context module where load_config is imported
    monkeypatch.setattr("affinity.cli.context.load_config", lambda _path: empty_config)

    runner = CliRunner()
    result = runner.invoke(cli, ["whoami"], env={"AFFINITY_API_KEY": ""})
    assert result.exit_code == 2
    assert "Missing API key." in result.output
    assert "Hint: run `affinity whoami --help`" not in result.output


def test_ambiguous_resolution_renders_match_table(capsys: pytest.CaptureFixture[str]) -> None:
    result = CommandResult(
        ok=False,
        command=CommandContext(name="list export"),
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


def test_normalize_exception_file_exists_adds_actionable_hint() -> None:
    exc = FileExistsError(17, "File exists", "/tmp/out.csv")
    normalized = normalize_exception(exc)
    assert normalized.error_type == "file_exists"
    assert normalized.exit_code == 2
    assert normalized.hint is not None
    assert "--overwrite" in normalized.hint


def test_error_info_includes_hint_and_renders(capsys: pytest.CaptureFixture[str]) -> None:
    exc = FileExistsError(17, "File exists", "/tmp/out.csv")
    info = error_info_for_exception(exc)
    assert info.type == "file_exists"
    assert info.hint is not None

    result = CommandResult(
        ok=False,
        command=CommandContext(name="list export"),
        data=None,
        artifacts=[],
        warnings=[],
        meta=CommandMeta(duration_ms=0, profile=None, resolved=None, pagination=None, columns=None),
        error=info,
    )
    render_result(
        result,
        settings=RenderSettings(output="table", quiet=False, verbosity=0, pager=False),
    )
    captured = capsys.readouterr()
    assert "File exists:" in captured.err
    assert "Hint:" in captured.err


def test_validation_error_normalization_includes_sanitized_params() -> None:
    exc = ValidationError(
        "Field organization_id: expected 2249254 to be a valid id",
        status_code=422,
        diagnostics=ErrorDiagnostics(
            method="GET",
            url="https://api.affinity.co/entity-files",
            request_params={"organization_id": "2249254", "term": "secret"},
        ),
    )
    normalized = normalize_exception(exc, verbosity=0)
    assert normalized.error_type == "validation_error"
    assert normalized.exit_code == 2
    assert normalized.hint is not None
    assert "company_id=2249254" in normalized.hint
    assert normalized.details is not None
    assert normalized.details.get("params") == {"organization_id": 2249254}
