from __future__ import annotations

import json

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

from click.testing import CliRunner

import affinity
from affinity.cli.main import cli


def test_cli_no_args_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cli_version_table_output() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert affinity.__version__ in result.output
    assert "Rate limit:" not in result.output


def test_cli_config_path_json_after_subcommand() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "path", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["ok"] is True
    assert payload["command"] == "config path"
    assert "path" in payload["data"]


def test_cli_completion_table_emits_script() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "bash"])
    assert result.exit_code == 0
    assert "_AFFINITY_COMPLETE" in result.output


def test_cli_completion_json_emits_command_result() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "bash", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["ok"] is True
    assert payload["command"] == "completion"
    assert payload["data"]["shell"] == "bash"
    assert "_AFFINITY_COMPLETE" in payload["data"]["script"]
