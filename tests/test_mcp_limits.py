"""Tests for MCP limit enforcement."""

from __future__ import annotations

import os
from unittest.mock import patch

import click
import pytest

from affinity.cli.mcp_limits import apply_mcp_limits, get_mcp_limits


class TestGetMcpLimits:
    def test_returns_none_when_not_in_mcp_context(self) -> None:
        # Remove only MCP-specific env vars (clear=True breaks pytest)
        env_without_mcp = {k: v for k, v in os.environ.items() if not k.startswith("AFFINITY_MCP_")}
        with patch.dict(os.environ, env_without_mcp, clear=True):
            max_limit, default_limit = get_mcp_limits()
            assert max_limit is None
            assert default_limit is None

    def test_returns_limits_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AFFINITY_MCP_MAX_LIMIT": "5000",
                "AFFINITY_MCP_DEFAULT_LIMIT": "500",
            },
        ):
            max_limit, default_limit = get_mcp_limits()
            assert max_limit == 5000
            assert default_limit == 500

    def test_returns_none_for_invalid_env_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AFFINITY_MCP_MAX_LIMIT": "not-a-number",
            },
        ):
            max_limit, default_limit = get_mcp_limits()
            assert max_limit is None
            assert default_limit is None

    def test_uses_default_for_missing_default_limit(self) -> None:
        # If only MAX_LIMIT is set, DEFAULT_LIMIT should fall back to 1000
        env_without_mcp = {k: v for k, v in os.environ.items() if not k.startswith("AFFINITY_MCP_")}
        env_without_mcp["AFFINITY_MCP_MAX_LIMIT"] = "10000"
        with patch.dict(os.environ, env_without_mcp, clear=True):
            max_limit, default_limit = get_mcp_limits()
            assert max_limit == 10000
            assert default_limit == 1000


class TestApplyMcpLimits:
    def test_no_enforcement_outside_mcp(self) -> None:
        @apply_mcp_limits()
        def cmd(max_results: int | None = None, all_pages: bool = False) -> tuple[int | None, bool]:
            return max_results, all_pages

        # Remove only MCP-specific env vars, don't clear all (which breaks pytest)
        env_without_mcp = {k: v for k, v in os.environ.items() if not k.startswith("AFFINITY_MCP_")}
        with patch.dict(os.environ, env_without_mcp, clear=True):
            assert cmd(max_results=99999) == (99999, False)
            assert cmd(all_pages=True) == (None, True)

    def test_blocks_all_pages_in_mcp(self) -> None:
        @apply_mcp_limits()
        def cmd(max_results: int | None = None, all_pages: bool = False) -> tuple[int | None, bool]:
            return max_results, all_pages

        with (
            patch.dict(os.environ, {"AFFINITY_MCP_MAX_LIMIT": "10000"}),
            pytest.raises(click.UsageError, match="--all is not allowed"),
        ):
            cmd(all_pages=True)

    def test_caps_limit_in_mcp(self) -> None:
        @apply_mcp_limits()
        def cmd(max_results: int | None = None, all_pages: bool = False) -> int | None:  # noqa: ARG001
            return max_results

        with patch.dict(os.environ, {"AFFINITY_MCP_MAX_LIMIT": "10000"}):
            assert cmd(max_results=50000) == 10000

    def test_injects_default_in_mcp(self) -> None:
        @apply_mcp_limits()
        def cmd(max_results: int | None = None, all_pages: bool = False) -> int | None:  # noqa: ARG001
            return max_results

        with patch.dict(
            os.environ,
            {
                "AFFINITY_MCP_MAX_LIMIT": "10000",
                "AFFINITY_MCP_DEFAULT_LIMIT": "1000",
            },
        ):
            assert cmd() == 1000

    def test_works_without_all_pages_param(self) -> None:
        """Test for commands like interaction_ls that don't have --all."""

        @apply_mcp_limits(all_pages_param=None)
        def cmd(max_results: int | None = None) -> int | None:
            return max_results

        with patch.dict(
            os.environ,
            {
                "AFFINITY_MCP_MAX_LIMIT": "10000",
                "AFFINITY_MCP_DEFAULT_LIMIT": "1000",
            },
        ):
            # Should inject default
            assert cmd() == 1000
            # Should cap high values
            assert cmd(max_results=50000) == 10000

    def test_preserves_explicit_limit_within_max(self) -> None:
        """Explicit limit within max should be preserved."""

        @apply_mcp_limits()
        def cmd(max_results: int | None = None, all_pages: bool = False) -> int | None:  # noqa: ARG001
            return max_results

        with patch.dict(
            os.environ,
            {
                "AFFINITY_MCP_MAX_LIMIT": "10000",
                "AFFINITY_MCP_DEFAULT_LIMIT": "1000",
            },
        ):
            assert cmd(max_results=500) == 500
            assert cmd(max_results=5000) == 5000
            assert cmd(max_results=10000) == 10000

    def test_custom_limit_param_name(self) -> None:
        """Test using custom parameter name."""

        @apply_mcp_limits(limit_param="limit")
        def cmd(limit: int | None = None, all_pages: bool = False) -> int | None:  # noqa: ARG001
            return limit

        with patch.dict(
            os.environ,
            {
                "AFFINITY_MCP_MAX_LIMIT": "10000",
                "AFFINITY_MCP_DEFAULT_LIMIT": "1000",
            },
        ):
            assert cmd() == 1000
            assert cmd(limit=50000) == 10000
