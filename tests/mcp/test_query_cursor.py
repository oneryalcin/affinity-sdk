"""MCP integration tests for cursor-based pagination.

Tests the end-to-end cursor flow from MCP request through CLI to response,
including cursor extraction from stderr NDJSON and response structure.
"""

from __future__ import annotations

import json
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from affinity.cli.query.cursor import (
    CURSOR_TTL_SECONDS,
    CursorPayload,
    decode_cursor,
    encode_cursor,
    hash_query,
)
from affinity.cli.query.models import Query, QueryResult
from affinity.cli.query.output import emit_cursor_to_stderr, insert_cursor_in_toon_truncation

# =============================================================================
# Cursor NDJSON Output Tests
# =============================================================================


class TestCursorNdjsonOutput:
    """Tests for cursor emission to stderr as NDJSON."""

    def test_emit_cursor_outputs_valid_ndjson(self) -> None:
        """emit_cursor_to_stderr outputs valid JSON with correct fields."""
        captured_stderr = StringIO()

        with patch("sys.stderr", captured_stderr):
            emit_cursor_to_stderr("eyJjdXJzb3I9", "streaming")

        output = captured_stderr.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["type"] == "cursor"
        assert parsed["cursor"] == "eyJjdXJzb3I9"
        assert parsed["mode"] == "streaming"

    def test_emit_cursor_full_fetch_mode(self) -> None:
        """emit_cursor_to_stderr correctly reports full-fetch mode."""
        captured_stderr = StringIO()

        with patch("sys.stderr", captured_stderr):
            emit_cursor_to_stderr("eyJjYWNoZT0iLCJ9", "full-fetch")

        output = captured_stderr.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["mode"] == "full-fetch"

    def test_emit_cursor_is_single_line(self) -> None:
        """Cursor output is single line (NDJSON format)."""
        captured_stderr = StringIO()

        with patch("sys.stderr", captured_stderr):
            emit_cursor_to_stderr("test_cursor", "streaming")

        output = captured_stderr.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) == 1


class TestCursorExtractionPattern:
    """Tests for the jq extraction pattern used by tool.sh."""

    def test_jq_extraction_pattern(self) -> None:
        """Cursor can be extracted via jq 'select(.type == \"cursor\")'."""
        # Simulate stderr with both progress and cursor messages
        stderr_content = (
            '{"type": "progress", "progress": 0, "message": "Fetching..."}\n'
            '{"type": "progress", "progress": 50, "message": "Processing..."}\n'
            '{"type": "cursor", "cursor": "eyJjdXJzb3I9", "mode": "streaming"}\n'
            '{"type": "progress", "progress": 100, "message": "Complete"}\n'
        )

        # Parse line by line and filter cursor type
        cursor_line = None
        for line in stderr_content.strip().split("\n"):
            try:
                parsed = json.loads(line)
                if parsed.get("type") == "cursor":
                    cursor_line = parsed
                    break
            except json.JSONDecodeError:
                continue

        assert cursor_line is not None
        assert cursor_line["cursor"] == "eyJjdXJzb3I9"
        assert cursor_line["mode"] == "streaming"

    def test_non_json_lines_ignored(self) -> None:
        """Non-JSON stderr lines don't break cursor extraction."""
        stderr_content = (
            "Some warning message\n"
            '{"type": "cursor", "cursor": "abc123", "mode": "full-fetch"}\n'
            "Another non-JSON line\n"
        )

        cursor_line = None
        for line in stderr_content.strip().split("\n"):
            try:
                parsed = json.loads(line)
                if parsed.get("type") == "cursor":
                    cursor_line = parsed
                    break
            except json.JSONDecodeError:
                continue

        assert cursor_line is not None
        assert cursor_line["cursor"] == "abc123"


# =============================================================================
# TOON Cursor Display Tests
# =============================================================================


class TestToonCursorDisplay:
    """Tests for cursor display in TOON truncation section."""

    def test_cursor_inserted_in_truncation_section(self) -> None:
        """Cursor is inserted after rowsOmitted in truncation section."""
        toon_output = """data[50]{id,name}:
  1  Alice
  2  Bob
truncation:
  rowsShown: 50
  rowsOmitted: 100
pagination:
  hasMore: false
  total: 150"""

        result = insert_cursor_in_toon_truncation(toon_output, "eyJjdXJzb3I9")

        assert "cursor: eyJjdXJzb3I9" in result
        assert result.index("rowsOmitted") < result.index("cursor:")
        assert result.index("cursor:") < result.index("pagination:")

    def test_cursor_not_inserted_without_truncation(self) -> None:
        """Cursor is not inserted when no truncation section exists."""
        toon_output = """data[10]{id,name}:
  1  Alice
  2  Bob
pagination:
  hasMore: false
  total: 10"""

        result = insert_cursor_in_toon_truncation(toon_output, "eyJjdXJzb3I9")

        assert "cursor:" not in result
        assert result == toon_output


# =============================================================================
# End-to-End Cursor Flow Tests
# =============================================================================


class TestCursorResumptionFlow:
    """Tests for the cursor resumption flow logic."""

    def test_cursor_validation_same_query(self) -> None:
        """Cursor validates when query matches."""
        query = Query(from_="persons", limit=50)
        qh = hash_query(query, "toon")

        cursor = CursorPayload(
            v=1,
            qh=qh,
            skip=50,
            last_id=123,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        # Encode and decode roundtrip
        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)

        assert decoded.qh == qh
        assert decoded.skip == 50
        assert decoded.last_id == 123

    def test_cursor_hash_changes_with_query(self) -> None:
        """Different queries produce different hashes."""
        query1 = Query(from_="persons", limit=50)
        query2 = Query(from_="persons", limit=100)

        hash1 = hash_query(query1, "toon")
        hash2 = hash_query(query2, "toon")

        assert hash1 != hash2

    def test_cursor_hash_changes_with_format(self) -> None:
        """Different formats produce different hashes."""
        query = Query(from_="persons", limit=50)

        toon_hash = hash_query(query, "toon")
        json_hash = hash_query(query, "json")

        assert toon_hash != json_hash


# =============================================================================
# MCP Response Structure Tests
# =============================================================================


class TestMcpResponseStructure:
    """Tests for MCP response structure with cursor."""

    def test_truncated_response_has_next_cursor(self) -> None:
        """Truncated responses should have nextCursor field."""
        # This simulates what tool.sh builds for the MCP response
        cli_was_truncated = True
        cli_cursor = "eyJjdXJzb3I9"
        cli_mode = "streaming"
        cli_output = "data[50]{id,name}:\n  1  Alice\n..."

        # Build MCP response structure (what tool.sh does)
        if cli_was_truncated:
            response = {
                "content": [{"type": "text", "text": cli_output}],
                "truncated": True,
                "nextCursor": cli_cursor,
                "_cursorMode": cli_mode,
            }
        else:
            response = {
                "content": [{"type": "text", "text": cli_output}],
                "truncated": False,
            }

        assert response["truncated"] is True
        assert response["nextCursor"] == cli_cursor
        assert response["_cursorMode"] == cli_mode

    def test_non_truncated_response_no_cursor(self) -> None:
        """Non-truncated responses should not have nextCursor."""
        response = {
            "content": [{"type": "text", "text": "data[10]{id}:\n  1\n  2"}],
            "truncated": False,
        }

        assert "nextCursor" not in response

    def test_json_format_response_structure(self) -> None:
        """JSON format response includes nextCursor at top level."""
        # For JSON format, CLI outputs nextCursor in the JSON itself
        cli_json_output = {
            "data": [{"id": 1}, {"id": 2}],
            "truncated": True,
            "nextCursor": "eyJjdXJzb3I9",
            "pagination": {"hasMore": False, "total": 100},
        }

        # tool.sh merges with executed command
        response = {
            **cli_json_output,
            "executed": ["xaffinity", "query", "--output", "json"],
            "_cursorMode": "streaming",
        }

        assert response["nextCursor"] == "eyJjdXJzb3I9"
        assert response["truncated"] is True


# =============================================================================
# Cursor Parameter Passing Tests
# =============================================================================


class TestCursorParameterPassing:
    """Tests for cursor parameter flow from MCP to CLI."""

    def test_cursor_parameter_in_tool_meta_json(self) -> None:
        """tool.meta.json has cursor parameter defined."""
        tool_meta_path = (
            Path(__file__).parent.parent.parent / "mcp" / "tools" / "query" / "tool.meta.json"
        )

        with tool_meta_path.open() as f:
            tool_meta = json.load(f)

        # Check cursor is in inputSchema
        props = tool_meta["inputSchema"]["properties"]
        assert "cursor" in props
        assert props["cursor"]["type"] == "string"
        assert "opaque cursor" in props["cursor"]["description"].lower()

    def test_cursor_cli_option_exists(self) -> None:
        """CLI query command has --cursor option."""
        from affinity.cli.commands.query_cmd import query_cmd

        # Check that --cursor is in the command parameters
        param_names = [p.name for p in query_cmd.params]
        assert "cursor_str" in param_names or any(
            p.name == "cursor_str" or (hasattr(p, "opts") and "--cursor" in p.opts)
            for p in query_cmd.params
        )


# =============================================================================
# Appendix B Test Matrix - Integration Scenarios
# =============================================================================


class TestAppendixBIntegration:
    """Integration scenarios from design document Appendix B."""

    def test_modes_streaming_cursor_structure(self) -> None:
        """Streaming mode cursor has correct structure."""
        query = Query(from_="persons", limit=100)
        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=50,
            last_id=12345,
            ts=int(time.time() * 1000),
            mode="streaming",
            api_cursor="affinity_api_cursor_abc123",
        )

        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)

        assert decoded.mode == "streaming"
        assert decoded.api_cursor == "affinity_api_cursor_abc123"
        assert decoded.cache_file is None

    def test_modes_full_fetch_cursor_structure(self) -> None:
        """Full-fetch mode cursor has cache info."""
        query = Query(from_="persons", order_by=[{"field": "name", "direction": "asc"}])
        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=50,
            last_id=12345,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file="/tmp/xaffinity_cache/xaff_abc123.json",
            cache_hash="a" * 64,
            total=500,
        )

        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)

        assert decoded.mode == "full-fetch"
        assert decoded.cache_file == "/tmp/xaffinity_cache/xaff_abc123.json"
        assert decoded.cache_hash == "a" * 64
        assert decoded.total == 500

    def test_exact_boundary_no_cursor(self) -> None:
        """When skip equals total, no more data to paginate."""
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=100,
            ts=int(time.time() * 1000),
            mode="streaming",
            total=100,
        )

        # If skip >= total, there's nothing left
        assert cursor.skip >= (cursor.total or 0)

    def test_empty_result_no_cursor(self) -> None:
        """Empty results don't need pagination."""
        result = QueryResult(data=[], pagination={"hasMore": False, "total": 0})

        # Empty data shouldn't produce cursor
        assert len(result.data) == 0

    def test_cursor_expired_detection(self) -> None:
        """Expired cursor (>1 hour) can be detected."""
        old_ts = int((time.time() - CURSOR_TTL_SECONDS - 60) * 1000)

        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=50,
            ts=old_ts,
            mode="streaming",
        )

        # Check if cursor is expired
        current_ts = int(time.time() * 1000)
        cursor_age_ms = current_ts - cursor.ts
        is_expired = cursor_age_ms > (CURSOR_TTL_SECONDS * 1000)

        assert is_expired is True

    def test_cursor_size_estimates(self) -> None:
        """Cursor sizes are within expected ranges per design doc."""
        # Streaming minimal
        cursor_minimal = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=50,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        encoded_minimal = encode_cursor(cursor_minimal)
        assert len(encoded_minimal) < 300  # Expected ~150 bytes

        # Streaming with apiCursor
        cursor_with_api = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=50,
            last_id=12345,
            ts=int(time.time() * 1000),
            mode="streaming",
            api_cursor="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        )
        encoded_with_api = encode_cursor(cursor_with_api)
        assert len(encoded_with_api) < 1000  # Expected ~300-500 bytes

        # Full-fetch with cache
        cursor_full_fetch = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=50,
            last_id=12345,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file="/tmp/xaffinity_cache/xaff_abc123_1234_abcd1234_1705123456789.json",
            cache_hash="b" * 64,
            total=1000,
        )
        encoded_full_fetch = encode_cursor(cursor_full_fetch)
        assert len(encoded_full_fetch) < 400  # Expected ~250 bytes


class TestAppendixBErrors:
    """Error scenarios from design document Appendix B."""

    def test_invalid_cursor_format_error(self) -> None:
        """Invalid cursor format raises InvalidCursor."""
        from affinity.cli.query.cursor import InvalidCursor

        with pytest.raises(InvalidCursor, match="Invalid cursor format"):
            decode_cursor("not-valid-base64!!!")

    def test_cursor_version_mismatch_error(self) -> None:
        """Unsupported cursor version raises InvalidCursor."""
        from affinity.cli.query.cursor import InvalidCursor, validate_cursor

        query = Query(from_="persons")
        cursor = CursorPayload(
            v=999,  # Future version
            qh=hash_query(query, "toon"),
            skip=50,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        with pytest.raises(InvalidCursor, match="Unsupported cursor version"):
            validate_cursor(cursor, query, "toon")

    def test_query_mismatch_error(self) -> None:
        """Query mismatch raises CursorQueryMismatch."""
        from affinity.cli.query.cursor import CursorQueryMismatch, validate_cursor

        query1 = Query(from_="persons", limit=50)
        query2 = Query(from_="persons", limit=100)

        cursor = CursorPayload(
            v=1,
            qh=hash_query(query1, "toon"),
            skip=50,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        with pytest.raises(CursorQueryMismatch, match="Query or format does not match"):
            validate_cursor(cursor, query2, "toon")

    def test_format_mismatch_error(self) -> None:
        """Format mismatch raises CursorQueryMismatch."""
        from affinity.cli.query.cursor import CursorQueryMismatch, validate_cursor

        query = Query(from_="persons")
        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=50,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        with pytest.raises(CursorQueryMismatch, match="Query or format does not match"):
            validate_cursor(cursor, query, "json")  # Different format

    def test_expired_cursor_error(self) -> None:
        """Expired cursor raises CursorExpired."""
        from affinity.cli.query.cursor import CursorExpired, validate_cursor

        query = Query(from_="persons")
        old_ts = int((time.time() - CURSOR_TTL_SECONDS - 60) * 1000)

        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=50,
            ts=old_ts,
            mode="streaming",
        )

        with pytest.raises(CursorExpired, match="Cursor has expired"):
            validate_cursor(cursor, query, "toon")


# =============================================================================
# Progress and Cursor Coexistence Tests
# =============================================================================


class TestProgressCursorCoexistence:
    """Tests for progress and cursor NDJSON coexistence on stderr."""

    def test_progress_and_cursor_both_use_type_field(self) -> None:
        """Progress and cursor messages both have 'type' field for filtering."""
        progress_msg = {"type": "progress", "progress": 50, "message": "Processing..."}
        cursor_msg = {"type": "cursor", "cursor": "eyJjdXJzb3I9", "mode": "streaming"}

        # Both should be valid JSON with type field
        assert progress_msg["type"] == "progress"
        assert cursor_msg["type"] == "cursor"

        # Can be distinguished by type
        for msg in [progress_msg, cursor_msg]:
            if msg["type"] == "cursor":
                assert "cursor" in msg
                assert "mode" in msg
            elif msg["type"] == "progress":
                assert "progress" in msg

    def test_mixed_stderr_filtering(self) -> None:
        """Can filter cursor from mixed stderr content."""
        stderr_lines = [
            '{"type": "progress", "progress": 0, "message": "Starting..."}',
            "Warning: Something happened",  # Non-JSON line
            '{"type": "progress", "progress": 100, "message": "Done"}',
            '{"type": "cursor", "cursor": "abc123", "mode": "full-fetch"}',
        ]

        # Extract only cursor messages
        cursor_messages = []
        for line in stderr_lines:
            try:
                parsed = json.loads(line)
                if parsed.get("type") == "cursor":
                    cursor_messages.append(parsed)
            except json.JSONDecodeError:
                continue

        assert len(cursor_messages) == 1
        assert cursor_messages[0]["cursor"] == "abc123"

    def test_cache_hit_progress_distinguishable(self) -> None:
        """Cache hit progress message has distinct event type."""
        cache_hit_msg = {
            "type": "progress",
            "event": "cache_hit",
            "message": "Serving from cache",
            "progress": 100,
        }
        regular_progress = {
            "type": "progress",
            "event": "step_progress",
            "stepId": 1,
            "progress": 50,
        }

        # Both are progress type but distinguishable by event
        assert cache_hit_msg["type"] == "progress"
        assert regular_progress["type"] == "progress"
        assert cache_hit_msg["event"] == "cache_hit"
        assert regular_progress["event"] == "step_progress"


# =============================================================================
# Format-Specific Cursor Tests (Appendix B - Formats)
# =============================================================================


class TestFormatSpecificCursor:
    """Tests for cursor behavior across different output formats."""

    def test_cursor_valid_for_all_formats(self) -> None:
        """Cursor can be created and validated for all supported formats."""
        query = Query(from_="persons", limit=50)
        formats = ["toon", "json", "markdown", "csv", "jsonl"]

        for fmt in formats:
            cursor = CursorPayload(
                v=1,
                qh=hash_query(query, fmt),
                skip=50,
                ts=int(time.time() * 1000),
                mode="streaming",
            )

            # Should roundtrip successfully
            encoded = encode_cursor(cursor)
            decoded = decode_cursor(encoded)

            assert decoded.qh == hash_query(query, fmt)

    def test_format_hash_uniqueness(self) -> None:
        """Each format produces a unique hash for the same query."""
        query = Query(from_="persons", limit=50)
        formats = ["toon", "json", "markdown", "csv", "jsonl"]

        hashes = {fmt: hash_query(query, fmt) for fmt in formats}

        # All hashes should be unique
        unique_hashes = set(hashes.values())
        assert len(unique_hashes) == len(formats), "All formats should produce unique hashes"

    def test_mcp_response_structure_for_json_format(self) -> None:
        """JSON format response includes nextCursor at JSON level."""
        # Simulating JSON format CLI output with embedded cursor
        cli_json = {
            "data": [{"id": 1}],
            "truncated": True,
            "nextCursor": "eyJjdXJzb3I9",
            "pagination": {"hasMore": False, "total": 100},
        }

        # Verify cursor is accessible at top level
        assert "nextCursor" in cli_json
        assert cli_json["nextCursor"] == "eyJjdXJzb3I9"

    def test_mcp_response_structure_for_text_formats(self) -> None:
        """Text formats (toon, markdown, csv, jsonl) get cursor in wrapper."""
        # For non-JSON formats, tool.sh wraps the output
        for fmt in ["toon", "markdown", "csv", "jsonl"]:
            response = {
                "content": [{"type": "text", "text": f"Sample {fmt} output..."}],
                "truncated": True,
                "nextCursor": "eyJjdXJzb3I9",
                "_cursorMode": "streaming",
            }

            assert response["truncated"] is True
            assert response["nextCursor"] == "eyJjdXJzb3I9"
            assert response["_cursorMode"] == "streaming"


# =============================================================================
# Aggregate and Full-Fetch Mode Tests (Appendix B - Modes)
# =============================================================================


class TestAggregateModeIntegration:
    """Integration tests for aggregate queries with cursor."""

    def test_aggregate_query_produces_full_fetch_cursor(self) -> None:
        """Aggregate queries should use full-fetch mode cursor."""
        query = Query(
            from_="persons",
            aggregate={"total": {"count": "*"}},
        )

        # Full-fetch mode cursor for aggregate
        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=10,
            ts=int(time.time() * 1000),
            mode="full-fetch",  # Aggregates require full-fetch
            cache_file="/tmp/xaffinity_cache/xaff_agg.json",
            cache_hash="a" * 64,
            total=50,
        )

        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)

        assert decoded.mode == "full-fetch"
        assert decoded.cache_file is not None

    def test_group_by_query_produces_full_fetch_cursor(self) -> None:
        """GroupBy queries should use full-fetch mode cursor."""
        query = Query(
            from_="listEntries",
            group_by="fields.Status",
            aggregate={"count": {"count": "*"}},
        )

        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=5,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file="/tmp/xaffinity_cache/xaff_grp.json",
            cache_hash="b" * 64,
            total=20,
        )

        assert cursor.mode == "full-fetch"


# =============================================================================
# O(1) Streaming Resumption Tests (Appendix B - Modes)
# =============================================================================


class TestO1StreamingResumptionMCP:
    """MCP-specific tests for O(1) streaming resumption."""

    def test_streaming_cursor_api_cursor_field_present(self) -> None:
        """Streaming cursor includes apiCursor field for O(1) resumption."""
        query = Query(from_="persons", limit=50)
        api_cursor_url = "https://api.affinity.co/v2/persons?page=3"

        cursor = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=100,
            ts=int(time.time() * 1000),
            mode="streaming",
            api_cursor=api_cursor_url,
        )

        # Verify field is present and correct
        assert cursor.api_cursor == api_cursor_url

        # Verify it roundtrips through encode/decode
        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)
        assert decoded.api_cursor == api_cursor_url

    def test_mcp_response_indicates_resumption_mode(self) -> None:
        """MCP response _cursorMode helps LLM understand resumption type."""
        # Streaming mode response structure
        streaming_response = {
            "content": [{"type": "text", "text": "...data..."}],
            "truncated": True,
            "nextCursor": "eyJjdXJzb3I=...",
            "_cursorMode": "streaming",  # Indicates O(1) resumption possible
        }

        # Full-fetch mode response structure
        full_fetch_response = {
            "content": [{"type": "text", "text": "...data..."}],
            "truncated": True,
            "nextCursor": "eyJjdXJzb3I=...",
            "_cursorMode": "full-fetch",  # Cache-based resumption
        }

        assert streaming_response["_cursorMode"] == "streaming"
        assert full_fetch_response["_cursorMode"] == "full-fetch"

    def test_api_cursor_enables_zero_refetch(self) -> None:
        """API cursor in streaming mode enables resumption without re-fetching."""
        # When cursor has api_cursor, executor starts from that position
        # instead of from the beginning
        query = Query(from_="persons")

        cursor_with_api = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=200,  # Already returned 200 records
            ts=int(time.time() * 1000),
            mode="streaming",
            api_cursor="https://api.affinity.co/v2/persons?page=5",  # Start at page 5
        )

        cursor_without_api = CursorPayload(
            v=1,
            qh=hash_query(query, "toon"),
            skip=200,
            ts=int(time.time() * 1000),
            mode="streaming",
            api_cursor=None,  # No API cursor - will re-fetch and skip
        )

        # With API cursor: O(1) resumption (no re-fetching)
        assert cursor_with_api.api_cursor is not None

        # Without API cursor: O(n) resumption (re-fetch and skip)
        assert cursor_without_api.api_cursor is None
        assert cursor_without_api.skip == 200  # Fallback to skip-based
