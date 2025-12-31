from __future__ import annotations

import io
import json
import os
import sys

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

from click.testing import CliRunner

import affinity
from affinity.cli.context import CLIContext
from affinity.cli.main import cli
from affinity.hooks import RequestInfo, RequestRetrying


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
    assert payload["command"]["name"] == "config path"
    assert "path" in payload["data"]


def test_cli_completion_table_emits_script() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "bash"])
    assert result.exit_code == 0
    assert "_XAFFINITY_COMPLETE" in result.output


def test_cli_completion_json_emits_command_result() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "bash", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["ok"] is True
    assert payload["command"]["name"] == "completion"
    assert payload["data"]["shell"] == "bash"
    assert "_XAFFINITY_COMPLETE" in payload["data"]["script"]


def test_rate_limit_visibility_on_event_handler() -> None:
    """Test that the CLI event handler prints rate limit messages to stderr."""
    # Create a minimal context
    ctx = CLIContext(
        output="json",
        quiet=False,
        verbosity=0,
        pager=None,
        progress="never",
        profile=None,
        dotenv=False,
        env_file=None,
        api_key_file=None,
        api_key_stdin=False,
        timeout=30.0,
        max_retries=3,
        readonly=False,
        trace=False,
        log_file=None,
        enable_log_file=False,
        enable_beta_endpoints=False,
    )

    warnings: list[str] = []
    # Provide a fake API key to get settings
    old_key = os.environ.get("AFFINITY_API_KEY")
    os.environ["AFFINITY_API_KEY"] = "test-key-for-rate-limit-test"
    try:
        settings = ctx.resolve_client_settings(warnings=warnings)
    finally:
        if old_key is not None:
            os.environ["AFFINITY_API_KEY"] = old_key
        else:
            os.environ.pop("AFFINITY_API_KEY", None)

    # Verify on_event is set
    assert settings.on_event is not None

    # Capture stderr to verify the message
    stderr_capture = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = stderr_capture

    try:
        # Create a RequestRetrying event
        event = RequestRetrying(
            client_request_id="test-123",
            request=RequestInfo(method="GET", url="https://api.affinity.co/v2/lists", headers={}),
            attempt=2,
            wait_seconds=60.5,
            reason="rate_limit",
        )

        # Fire the event
        settings.on_event(event)
    finally:
        sys.stderr = old_stderr

    # Verify the message was written
    output = stderr_capture.getvalue()
    assert "Rate limited (429)" in output
    assert "retrying in 60s" in output
