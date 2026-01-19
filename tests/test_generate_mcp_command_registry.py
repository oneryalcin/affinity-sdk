"""Tests for MCP registry generator limit config logic."""

from __future__ import annotations

from tools.generate_mcp_command_registry import add_limit_config, get_param_with_aliases


class TestGetParamWithAliases:
    def test_finds_canonical_flag(self) -> None:
        params = {
            "--max-results": {"type": "int", "aliases": ["--limit", "-n"]},
        }
        result = get_param_with_aliases(params, "--max-results")
        assert result == ("--max-results", ["--max-results", "--limit", "-n"])

    def test_finds_flag_by_alias(self) -> None:
        params = {
            "--max-results": {"type": "int", "aliases": ["--limit", "-n"]},
        }
        result = get_param_with_aliases(params, "--limit")
        assert result == ("--max-results", ["--max-results", "--limit", "-n"])

    def test_finds_flag_by_short_alias(self) -> None:
        params = {
            "--max-results": {"type": "int", "aliases": ["--limit", "-n"]},
        }
        result = get_param_with_aliases(params, "-n")
        assert result == ("--max-results", ["--max-results", "--limit", "-n"])

    def test_returns_none_for_missing_flag(self) -> None:
        params = {
            "--other": {"type": "flag"},
        }
        assert get_param_with_aliases(params, "--max-results") is None

    def test_handles_param_without_aliases(self) -> None:
        params = {
            "--max-results": {"type": "int"},
        }
        result = get_param_with_aliases(params, "--max-results")
        assert result == ("--max-results", ["--max-results"])


class TestAddLimitConfig:
    def test_adds_limit_config_with_all_flag(self) -> None:
        cmd: dict[str, object] = {
            "name": "list export",
            "parameters": {
                "--max-results": {"type": "int", "aliases": ["--limit", "-n"]},
                "--all": {"type": "flag", "aliases": ["-A"]},
            },
        }
        add_limit_config(cmd)

        assert "limitConfig" in cmd
        limit_config = cmd["limitConfig"]
        assert isinstance(limit_config, dict)
        assert limit_config["flag"] == "--max-results"
        assert limit_config["unboundedFlag"] == "--all"
        assert limit_config["unboundedFlagAliases"] == ["--all", "-A"]
        assert limit_config["default"] == 1000
        assert limit_config["max"] == 10000

    def test_adds_limit_config_without_all_flag(self) -> None:
        cmd: dict[str, object] = {
            "name": "interaction ls",
            "parameters": {
                "--max-results": {"type": "int", "aliases": ["--limit", "-n"]},
            },
        }
        add_limit_config(cmd)

        assert "limitConfig" in cmd
        limit_config = cmd["limitConfig"]
        assert isinstance(limit_config, dict)
        assert "unboundedFlag" not in limit_config
        assert "unboundedFlagAliases" not in limit_config
        assert limit_config["flag"] == "--max-results"

    def test_no_limit_config_without_limit_param(self) -> None:
        cmd: dict[str, object] = {
            "name": "person get",
            "parameters": {
                "--expand": {"type": "string"},
            },
        }
        add_limit_config(cmd)

        assert "limitConfig" not in cmd

    def test_falls_back_to_limit_flag(self) -> None:
        """If --max-results not present, should check for --limit."""
        cmd: dict[str, object] = {
            "name": "some cmd",
            "parameters": {
                "--limit": {"type": "int"},
            },
        }
        add_limit_config(cmd)

        assert "limitConfig" in cmd
        limit_config = cmd["limitConfig"]
        assert isinstance(limit_config, dict)
        assert limit_config["flag"] == "--limit"

    def test_handles_empty_parameters(self) -> None:
        cmd: dict[str, object] = {
            "name": "some cmd",
            "parameters": {},
        }
        add_limit_config(cmd)

        assert "limitConfig" not in cmd

    def test_handles_missing_parameters(self) -> None:
        cmd: dict[str, object] = {
            "name": "some cmd",
        }
        add_limit_config(cmd)

        assert "limitConfig" not in cmd
