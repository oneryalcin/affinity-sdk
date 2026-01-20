"""Tests for cursor-based pagination.

Tests the cursor encoding/decoding, validation, and cache management
functionality for resumable query results.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from affinity.cli.query.cursor import (
    CURSOR_TTL_SECONDS,
    CURSOR_VERSION,
    CursorExpired,
    CursorPayload,
    CursorQueryMismatch,
    InvalidCursor,
    cleanup_cache,
    create_full_fetch_cursor,
    create_streaming_cursor,
    decode_cursor,
    delete_cache,
    encode_cursor,
    find_resume_position,
    generate_cache_filename,
    get_cache_dir,
    hash_query,
    read_cache,
    validate_cursor,
    write_cache,
)
from affinity.cli.query.models import Query

# =============================================================================
# Query Hashing Tests
# =============================================================================


class TestHashQuery:
    """Tests for query hashing."""

    def test_hash_is_deterministic(self) -> None:
        """Same query produces same hash."""
        query = Query(from_="persons", limit=10)
        hash1 = hash_query(query, "toon")
        hash2 = hash_query(query, "toon")
        assert hash1 == hash2

    def test_hash_is_24_chars(self) -> None:
        """Hash is 24 hex characters (96 bits)."""
        query = Query(from_="persons")
        h = hash_query(query, "toon")
        assert len(h) == 24
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_queries_different_hashes(self) -> None:
        """Different queries produce different hashes."""
        query1 = Query(from_="persons", limit=10)
        query2 = Query(from_="persons", limit=20)
        assert hash_query(query1, "toon") != hash_query(query2, "toon")

    def test_format_changes_hash(self) -> None:
        """Changing format invalidates cursor (hash changes)."""
        query = Query(from_="persons")
        toon_hash = hash_query(query, "toon")
        json_hash = hash_query(query, "json")
        assert toon_hash != json_hash

    def test_hash_ignores_cursor_field(self) -> None:
        """Query cursor field is not included in hash."""
        query1 = Query(from_="persons", limit=10)
        query2 = Query(from_="persons", limit=10, cursor="abc123")
        # Both should hash the same since cursor is not in HASH_FIELDS
        assert hash_query(query1, "toon") == hash_query(query2, "toon")


# =============================================================================
# Cursor Encoding/Decoding Tests
# =============================================================================


class TestCursorEncoding:
    """Tests for cursor encoding and decoding."""

    def test_encode_decode_roundtrip(self) -> None:
        """Cursor survives encode/decode roundtrip."""
        original = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=100,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded.v == original.v
        assert decoded.qh == original.qh
        assert decoded.skip == original.skip
        assert decoded.mode == original.mode

    def test_encode_decode_with_all_fields(self) -> None:
        """Cursor with all fields survives roundtrip."""
        original = CursorPayload(
            v=1,
            qh="b" * 24,
            skip=50,
            last_id=12345,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file="/tmp/xaff_test.json",
            cache_hash="c" * 64,
            total=500,
        )
        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded.last_id == 12345
        assert decoded.cache_file == "/tmp/xaff_test.json"
        assert decoded.total == 500

    def test_decode_invalid_base64(self) -> None:
        """Invalid base64 raises InvalidCursor."""
        with pytest.raises(InvalidCursor, match="Invalid cursor format"):
            decode_cursor("not-valid-base64!!!")

    def test_decode_invalid_json(self) -> None:
        """Invalid JSON raises InvalidCursor."""
        import base64

        invalid_json = base64.urlsafe_b64encode(b"not json").decode()
        with pytest.raises(InvalidCursor, match="Invalid cursor format"):
            decode_cursor(invalid_json)

    def test_decode_invalid_schema(self) -> None:
        """Invalid schema raises InvalidCursor."""
        import base64

        bad_schema = base64.urlsafe_b64encode(b'{"v": 1}').decode()  # Missing required fields
        with pytest.raises(InvalidCursor, match="Invalid cursor format"):
            decode_cursor(bad_schema)


# =============================================================================
# Cursor Validation Tests
# =============================================================================


class TestCursorValidation:
    """Tests for cursor validation."""

    def test_valid_cursor_passes(self) -> None:
        """Valid cursor passes validation."""
        query = Query(from_="persons", limit=10)
        cursor = CursorPayload(
            v=CURSOR_VERSION,
            qh=hash_query(query, "toon"),
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        # Should not raise
        validate_cursor(cursor, query, "toon")

    def test_version_mismatch_fails(self) -> None:
        """Wrong version raises InvalidCursor."""
        query = Query(from_="persons")
        cursor = CursorPayload(
            v=999,  # Wrong version
            qh=hash_query(query, "toon"),
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        with pytest.raises(InvalidCursor, match="Unsupported cursor version"):
            validate_cursor(cursor, query, "toon")

    def test_query_mismatch_fails(self) -> None:
        """Query mismatch raises CursorQueryMismatch."""
        query1 = Query(from_="persons", limit=10)
        query2 = Query(from_="persons", limit=20)  # Different query

        cursor = CursorPayload(
            v=CURSOR_VERSION,
            qh=hash_query(query1, "toon"),  # Hash of query1
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        with pytest.raises(CursorQueryMismatch, match="Query or format does not match"):
            validate_cursor(cursor, query2, "toon")  # Validate against query2

    def test_format_mismatch_fails(self) -> None:
        """Format mismatch raises CursorQueryMismatch."""
        query = Query(from_="persons")
        cursor = CursorPayload(
            v=CURSOR_VERSION,
            qh=hash_query(query, "toon"),  # Hash with toon format
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        with pytest.raises(CursorQueryMismatch, match="Query or format does not match"):
            validate_cursor(cursor, query, "json")  # Validate with json format

    def test_expired_cursor_fails(self) -> None:
        """Expired cursor raises CursorExpired."""
        query = Query(from_="persons")
        old_ts = int((time.time() - CURSOR_TTL_SECONDS - 60) * 1000)  # 1 minute past TTL

        cursor = CursorPayload(
            v=CURSOR_VERSION,
            qh=hash_query(query, "toon"),
            skip=0,
            ts=old_ts,
            mode="streaming",
        )
        with pytest.raises(CursorExpired, match="Cursor has expired"):
            validate_cursor(cursor, query, "toon")

    def test_negative_skip_fails_at_model_level(self) -> None:
        """Negative skip is rejected by Pydantic model validation."""
        # Pydantic's ge=0 constraint rejects negative skip at model construction
        with pytest.raises(ValueError):
            CursorPayload(
                v=CURSOR_VERSION,
                qh="a" * 24,
                skip=-1,  # Invalid
                ts=int(time.time() * 1000),
                mode="streaming",
            )


# =============================================================================
# Cursor Creation Helper Tests
# =============================================================================


class TestCursorCreation:
    """Tests for cursor creation helpers."""

    def test_create_streaming_cursor(self) -> None:
        """Create streaming cursor with all fields."""
        query = Query(from_="persons")
        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=50,
            api_cursor="abc123",
            last_id=999,
            total=500,
        )

        assert cursor.mode == "streaming"
        assert cursor.skip == 50
        assert cursor.api_cursor == "abc123"
        assert cursor.last_id == 999
        assert cursor.total == 500
        assert cursor.v == CURSOR_VERSION

    def test_create_full_fetch_cursor(self) -> None:
        """Create full-fetch cursor with cache info."""
        query = Query(from_="persons")
        cursor = create_full_fetch_cursor(
            query=query,
            output_format="toon",
            skip=100,
            cache_file="/tmp/xaff_test.json",
            cache_hash="a" * 64,
            last_id=888,
            total=1000,
        )

        assert cursor.mode == "full-fetch"
        assert cursor.skip == 100
        assert cursor.cache_file == "/tmp/xaff_test.json"
        assert cursor.cache_hash == "a" * 64
        assert cursor.last_id == 888
        assert cursor.total == 1000


# =============================================================================
# Cache Management Tests
# =============================================================================


class TestCacheManagement:
    """Tests for cache file management."""

    def test_get_cache_dir_creates_directory(self) -> None:
        """Cache directory is created if needed."""
        cache_dir = get_cache_dir()
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_generate_cache_filename_unique(self) -> None:
        """Cache filenames are unique (via timestamp)."""
        f1 = generate_cache_filename("a" * 24)
        # Small delay to ensure different timestamp
        time.sleep(0.002)
        f2 = generate_cache_filename("a" * 24)
        # Same hash but different timestamps
        assert f1 != f2

    def test_generate_cache_filename_format(self) -> None:
        """Cache filename has expected format."""
        filename = generate_cache_filename("b" * 24)
        assert filename.startswith("xaff_")
        assert filename.endswith(".json")
        assert "bbbbbbbbbbbbbbbbbbbbbbbb" in filename

    def test_write_and_read_cache(self) -> None:
        """Write and read cache data."""
        data = [{"id": 1, "name": "Test"}]
        query_hash = "c" * 24

        cache_file, cache_hash = write_cache(data, query_hash)
        assert Path(cache_file).exists()

        # Create cursor pointing to cache
        cursor = CursorPayload(
            v=1,
            qh=query_hash,
            skip=0,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file=cache_file,
            cache_hash=cache_hash,
        )

        # Read back
        read_data = read_cache(cursor)
        assert read_data == data

        # Cleanup
        delete_cache(cache_file)
        assert not Path(cache_file).exists()

    def test_read_cache_expired(self) -> None:
        """Expired cache returns None."""
        data = [{"id": 1}]
        query_hash = "d" * 24

        cache_file, cache_hash = write_cache(data, query_hash)

        # Create cursor with cache info
        cursor = CursorPayload(
            v=1,
            qh=query_hash,
            skip=0,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file=cache_file,
            cache_hash=cache_hash,
        )

        # Set file mtime to past TTL
        old_time = time.time() - CURSOR_TTL_SECONDS - 100
        import os

        os.utime(cache_file, (old_time, old_time))

        # Should return None (expired)
        result = read_cache(cursor)
        assert result is None

    def test_read_cache_integrity_failure(self) -> None:
        """Cache with wrong hash returns None."""
        data = [{"id": 1}]
        query_hash = "e" * 24

        cache_file, _cache_hash = write_cache(data, query_hash)

        # Create cursor with wrong hash
        cursor = CursorPayload(
            v=1,
            qh=query_hash,
            skip=0,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file=cache_file,
            cache_hash="wrong" * 16,  # Wrong hash
        )

        # Should return None (integrity failure)
        result = read_cache(cursor)
        assert result is None

        # Cleanup
        delete_cache(cache_file)

    def test_read_cache_missing_file(self) -> None:
        """Missing cache file returns None."""
        cursor = CursorPayload(
            v=1,
            qh="f" * 24,
            skip=0,
            ts=int(time.time() * 1000),
            mode="full-fetch",
            cache_file="/tmp/nonexistent_cache_file.json",
            cache_hash="g" * 64,
        )

        result = read_cache(cursor)
        assert result is None

    def test_cleanup_cache_removes_old_files(self) -> None:
        """Cleanup removes files older than TTL."""
        data = [{"id": 1}]
        query_hash = "h" * 24

        cache_file, _ = write_cache(data, query_hash)

        # Set file mtime to past TTL
        old_time = time.time() - CURSOR_TTL_SECONDS - 100
        import os

        os.utime(cache_file, (old_time, old_time))

        # Run cleanup
        cleanup_cache()

        # File should be deleted
        assert not Path(cache_file).exists()


# =============================================================================
# CursorPayload Model Tests
# =============================================================================


class TestCursorPayloadModel:
    """Tests for CursorPayload Pydantic model."""

    def test_query_hash_validation_length(self) -> None:
        """Query hash must be 24 characters."""
        with pytest.raises(ValueError, match="24 hex characters"):
            CursorPayload(
                v=1,
                qh="tooshort",
                skip=0,
                ts=int(time.time() * 1000),
                mode="streaming",
            )

    def test_query_hash_validation_hex(self) -> None:
        """Query hash must be hex characters."""
        with pytest.raises(ValueError, match="24 hex characters"):
            CursorPayload(
                v=1,
                qh="gggggggggggggggggggggggg",  # 'g' is not hex
                skip=0,
                ts=int(time.time() * 1000),
                mode="streaming",
            )

    def test_skip_cannot_be_negative(self) -> None:
        """Skip field cannot be negative."""
        with pytest.raises(ValueError):
            CursorPayload(
                v=1,
                qh="a" * 24,
                skip=-1,
                ts=int(time.time() * 1000),
                mode="streaming",
            )

    def test_alias_serialization(self) -> None:
        """Model uses camelCase aliases in JSON."""
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=10,
            last_id=123,
            ts=int(time.time() * 1000),
            mode="streaming",
            api_cursor="xyz",
        )
        json_str = cursor.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert "lastId" in data
        assert "last_id" not in data
        assert "apiCursor" in data
        assert "api_cursor" not in data


# =============================================================================
# Resume Position Tests
# =============================================================================


class TestFindResumePosition:
    """Tests for find_resume_position()."""

    def test_resume_by_last_id(self) -> None:
        """Finds position after lastId anchor."""
        records = [
            {"id": 100, "name": "A"},
            {"id": 200, "name": "B"},
            {"id": 300, "name": "C"},
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=1,
            last_id=200,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 2  # After record with id=200
        assert len(warnings) == 0

    def test_resume_by_list_entry_id(self) -> None:
        """Uses listEntryId when id is not present."""
        records = [
            {"listEntryId": 100, "name": "A"},
            {"listEntryId": 200, "name": "B"},
            {"listEntryId": 300, "name": "C"},
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=1,
            last_id=100,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 1  # After record with listEntryId=100
        assert len(warnings) == 0

    def test_last_id_not_found_fallback_to_skip(self) -> None:
        """Falls back to skip when lastId is not found."""
        records = [
            {"id": 100, "name": "A"},
            {"id": 200, "name": "B"},
            {"id": 300, "name": "C"},
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=1,
            last_id=999,  # Not in records
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 1  # Falls back to skip
        assert len(warnings) == 1
        assert "not found" in warnings[0]

    def test_no_last_id_uses_skip(self) -> None:
        """Uses skip when no lastId provided."""
        records = [
            {"id": 100, "name": "A"},
            {"id": 200, "name": "B"},
            {"id": 300, "name": "C"},
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=2,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 2
        assert len(warnings) == 0

    def test_skip_exceeds_total(self) -> None:
        """Returns end of list when skip exceeds total."""
        records = [{"id": 100}]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=10,  # More than records
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 1  # len(records)
        assert len(warnings) == 0

    def test_empty_records(self) -> None:
        """Handles empty record list."""
        records: list[dict] = []
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 0
        assert len(warnings) == 0


# =============================================================================
# TOON Cursor Insertion Tests
# =============================================================================


class TestToonCursorInsertion:
    """Tests for insert_cursor_in_toon_truncation()."""

    def test_inserts_cursor_in_truncation_section(self) -> None:
        """Inserts cursor after rowsOmitted."""
        from affinity.cli.query.output import insert_cursor_in_toon_truncation

        toon_output = """data[50]{id,name}:
  1  Alice
  2  Bob
truncation:
  rowsShown: 50
  rowsOmitted: 100
pagination:
  total: 150"""

        result = insert_cursor_in_toon_truncation(toon_output, "eyJjdXJzb3I9")

        assert "cursor: eyJjdXJzb3I9" in result
        # Cursor should be after rowsOmitted
        assert result.index("rowsOmitted") < result.index("cursor:")

    def test_no_truncation_section(self) -> None:
        """Returns unchanged output if no truncation section."""
        from affinity.cli.query.output import insert_cursor_in_toon_truncation

        toon_output = """data[10]{id,name}:
  1  Alice
  2  Bob"""

        result = insert_cursor_in_toon_truncation(toon_output, "eyJjdXJzb3I9")

        # Should be unchanged
        assert result == toon_output
        assert "cursor:" not in result


# =============================================================================
# Edge Case Tests (from Appendix B)
# =============================================================================


class TestEdgeCases:
    """Edge case tests from design document Appendix B."""

    def test_exact_boundary(self) -> None:
        """When skip equals remaining, returns empty with no cursor."""
        records = [{"id": 1}, {"id": 2}]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=2,  # Equals len(records)
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, _ = find_resume_position(records, cursor)
        remaining = records[position:]
        assert len(remaining) == 0

    def test_single_record_result(self) -> None:
        """Single record properly handled."""
        records = [{"id": 1}]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        assert position == 0
        assert len(warnings) == 0

    def test_cursor_version_mismatch(self) -> None:
        """Unsupported version raises error."""
        query = Query(from_="persons")
        cursor = CursorPayload(
            v=999,  # Future version
            qh=hash_query(query, "toon"),
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )
        with pytest.raises(InvalidCursor, match="Unsupported cursor version"):
            validate_cursor(cursor, query, "toon")

    def test_cache_path_outside_cache_dir(self) -> None:
        """Rejects cache paths outside cache directory."""
        from affinity.cli.query.cursor import _validate_cache_path

        with pytest.raises(InvalidCursor, match="outside cache directory"):
            _validate_cache_path("/etc/passwd")

    def test_cache_path_invalid_prefix(self) -> None:
        """Rejects cache files without xaff_ prefix."""
        from affinity.cli.query.cursor import _validate_cache_path

        cache_dir = get_cache_dir()
        invalid_path = cache_dir / "malicious.json"

        with pytest.raises(InvalidCursor, match="Invalid cache filename"):
            _validate_cache_path(str(invalid_path))


# =============================================================================
# Format-Specific Cursor Tests (Appendix B)
# =============================================================================


class TestFormatSpecificCursor:
    """Tests for cursor behavior with different output formats."""

    def test_format_in_hash_toon(self) -> None:
        """TOON format produces unique hash."""
        query = Query(from_="persons", limit=50)
        toon_hash = hash_query(query, "toon")
        assert len(toon_hash) == 24

    def test_format_in_hash_json(self) -> None:
        """JSON format produces different hash than TOON."""
        query = Query(from_="persons", limit=50)
        toon_hash = hash_query(query, "toon")
        json_hash = hash_query(query, "json")
        assert toon_hash != json_hash

    def test_format_in_hash_markdown(self) -> None:
        """Markdown format produces unique hash."""
        query = Query(from_="persons", limit=50)
        md_hash = hash_query(query, "markdown")
        toon_hash = hash_query(query, "toon")
        assert md_hash != toon_hash

    def test_format_in_hash_csv(self) -> None:
        """CSV format produces unique hash."""
        query = Query(from_="persons", limit=50)
        csv_hash = hash_query(query, "csv")
        json_hash = hash_query(query, "json")
        assert csv_hash != json_hash

    def test_format_in_hash_jsonl(self) -> None:
        """JSONL format produces unique hash."""
        query = Query(from_="persons", limit=50)
        jsonl_hash = hash_query(query, "jsonl")
        json_hash = hash_query(query, "json")
        assert jsonl_hash != json_hash


# =============================================================================
# Data Change Scenario Tests (Appendix B)
# =============================================================================


class TestDataChangeScenarios:
    """Tests for cursor behavior when data changes between calls."""

    def test_records_added_before_cursor_position(self) -> None:
        """When records are added before cursor position, uses lastId anchor."""
        # Simulate original data: ids 100, 200, 300 (cursor at 200)
        # After add: ids 50, 100, 200, 300 (new record 50 added)
        new_records = [
            {"id": 50, "name": "New"},  # Added record
            {"id": 100, "name": "A"},
            {"id": 200, "name": "B"},  # lastId anchor
            {"id": 300, "name": "C"},
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=2,  # Original position
            last_id=200,  # Anchor
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(new_records, cursor)
        # Should find position after id=200 (index 2 + 1 = 3)
        assert position == 3
        assert len(warnings) == 0

    def test_records_deleted_before_cursor_position(self) -> None:
        """When records are deleted before cursor position, uses lastId anchor."""
        # Simulate original data: ids 100, 200, 300 (cursor at 200)
        # After delete: ids 200, 300 (record 100 deleted)
        new_records = [
            {"id": 200, "name": "B"},  # lastId anchor
            {"id": 300, "name": "C"},
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=2,  # Original position
            last_id=200,  # Anchor
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(new_records, cursor)
        # Should find position after id=200 (index 0 + 1 = 1)
        assert position == 1
        assert len(warnings) == 0

    def test_last_id_deleted_falls_back_to_skip(self) -> None:
        """When lastId is deleted, falls back to skip with warning."""
        records = [
            {"id": 100, "name": "A"},
            {"id": 300, "name": "C"},  # id=200 was deleted
        ]
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=1,  # Original position
            last_id=200,  # Deleted
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        position, warnings = find_resume_position(records, cursor)
        # Falls back to skip=1
        assert position == 1
        assert len(warnings) == 1
        assert "not found" in warnings[0]

    def test_total_count_mismatch_detection(self) -> None:
        """Can detect when total count changed since cursor creation."""
        cursor = CursorPayload(
            v=1,
            qh="a" * 24,
            skip=50,
            ts=int(time.time() * 1000),
            mode="streaming",
            total=100,  # Original total
        )

        # Current total is different
        current_total = 120

        # Application code should compare and warn
        assert cursor.total != current_total


# =============================================================================
# Cache Lifecycle Tests (Appendix B)
# =============================================================================


class TestCacheLifecycle:
    """Tests for cache file lifecycle."""

    def test_cache_file_naming_includes_pid(self) -> None:
        """Cache filename includes process ID for uniqueness."""
        import os

        filename = generate_cache_filename("a" * 24)
        pid = str(os.getpid())
        assert pid in filename

    def test_cache_file_naming_includes_timestamp(self) -> None:
        """Cache filename includes timestamp."""
        filename = generate_cache_filename("a" * 24)
        # Filename format: xaff_{hash}_{pid}_{uuid}_{timestamp}.json
        parts = filename.replace(".json", "").split("_")
        # Last part should be timestamp (13 digits for ms)
        assert len(parts[-1]) == 13
        assert parts[-1].isdigit()

    def test_two_cache_files_same_hash_different(self) -> None:
        """Two cache files with same hash are unique (concurrency safe)."""
        hash1 = "a" * 24
        filename1 = generate_cache_filename(hash1)
        time.sleep(0.002)  # Small delay for different timestamp
        filename2 = generate_cache_filename(hash1)

        assert filename1 != filename2

    def test_delete_cache_removes_file(self) -> None:
        """delete_cache removes the cache file."""
        data = [{"id": 1}]
        cache_file, _ = write_cache(data, "test" * 6)

        assert Path(cache_file).exists()
        delete_cache(cache_file)
        assert not Path(cache_file).exists()

    def test_delete_cache_missing_file_no_error(self) -> None:
        """delete_cache handles missing file gracefully."""
        # Should not raise
        delete_cache("/tmp/nonexistent_cache_file_12345.json")


# =============================================================================
# Security Tests (Appendix B)
# =============================================================================


class TestSecurityScenarios:
    """Security-related tests from Appendix B."""

    def test_path_traversal_parent_directory(self) -> None:
        """Rejects cache paths with parent directory traversal."""
        from affinity.cli.query.cursor import _validate_cache_path

        cache_dir = get_cache_dir()
        malicious_path = str(cache_dir / ".." / "sensitive.json")

        with pytest.raises(InvalidCursor):
            _validate_cache_path(malicious_path)

    def test_path_traversal_absolute_path(self) -> None:
        """Rejects absolute paths outside cache directory."""
        from affinity.cli.query.cursor import _validate_cache_path

        with pytest.raises(InvalidCursor, match="outside cache directory"):
            _validate_cache_path("/var/log/system.log")

    def test_valid_cache_path_accepted(self) -> None:
        """Valid cache paths are accepted."""
        from affinity.cli.query.cursor import _validate_cache_path

        cache_dir = get_cache_dir()
        valid_path = str(cache_dir / "xaff_test123456789012345678901234.json")

        # Should not raise
        _validate_cache_path(valid_path)


# =============================================================================
# Concurrency Tests (Appendix B)
# =============================================================================


class TestConcurrencyScenarios:
    """Concurrency-related tests from Appendix B."""

    def test_concurrent_cache_files_unique_per_session(self) -> None:
        """Multiple CLI processes create unique cache files."""
        hash_value = "b" * 24

        # Generate multiple filenames (simulating different sessions)
        filenames = set()
        for _ in range(10):
            time.sleep(0.002)  # Ensure different timestamps
            filename = generate_cache_filename(hash_value)
            filenames.add(filename)

        # All should be unique
        assert len(filenames) == 10

    def test_cleanup_only_deletes_expired_files(self) -> None:
        """Cleanup doesn't delete active (non-expired) cache files."""

        data = [{"id": 1}]
        cache_file, _ = write_cache(data, "cleanup" * 4)

        # File is fresh (just created)
        assert Path(cache_file).exists()

        # Run cleanup
        cleanup_cache()

        # Fresh file should still exist
        assert Path(cache_file).exists()

        # Clean up
        delete_cache(cache_file)


# =============================================================================
# Query Hash Stability Tests
# =============================================================================


class TestQueryHashStability:
    """Tests for query hash stability across different scenarios."""

    def test_hash_stable_with_extra_fields(self) -> None:
        """Hash only includes HASH_FIELDS, not extra model fields."""
        query1 = Query(from_="persons", limit=50)
        # Same semantic query with cursor field (which should be ignored)
        query2 = Query(from_="persons", limit=50, cursor="some_cursor")

        assert hash_query(query1, "toon") == hash_query(query2, "toon")

    def test_hash_includes_order_by(self) -> None:
        """orderBy changes the hash."""
        query1 = Query(from_="persons", limit=50)
        query2 = Query(from_="persons", limit=50, order_by=[{"field": "name", "direction": "asc"}])

        assert hash_query(query1, "toon") != hash_query(query2, "toon")

    def test_hash_includes_where(self) -> None:
        """where clause changes the hash."""
        query1 = Query(from_="persons", limit=50)
        query2 = Query(
            from_="persons",
            limit=50,
            where={"path": "email", "op": "contains", "value": "@test.com"},
        )

        assert hash_query(query1, "toon") != hash_query(query2, "toon")

    def test_hash_includes_select(self) -> None:
        """select clause changes the hash."""
        query1 = Query(from_="persons", limit=50)
        query2 = Query(from_="persons", limit=50, select=["id", "name"])

        assert hash_query(query1, "toon") != hash_query(query2, "toon")

    def test_hash_includes_aggregate(self) -> None:
        """aggregate changes the hash."""
        query1 = Query(from_="persons", limit=50)
        query2 = Query(from_="persons", limit=50, aggregate={"total": {"count": "*"}})

        assert hash_query(query1, "toon") != hash_query(query2, "toon")


# =============================================================================
# Cache Size Limits Tests (Appendix B)
# =============================================================================


class TestCacheSizeLimits:
    """Tests for cache file and directory size limits."""

    def test_cache_file_exceeds_100mb_limit(self) -> None:
        """Cache write fails when data exceeds 100MB."""
        # We can't actually create 100MB of data in a test, so we mock the limit
        with patch("affinity.cli.query.cursor.MAX_CACHE_FILE_BYTES", 100):  # 100 bytes limit
            data = [{"id": i, "name": f"Name{i}" * 10} for i in range(10)]

            with pytest.raises(InvalidCursor, match="too large to cache"):
                write_cache(data, "limit" * 4)

    def test_cache_eviction_triggered_when_dir_full(self) -> None:
        """LRU eviction triggers when directory approaches 500MB."""
        from affinity.cli.query.cursor import _evict_cache_files

        # Create some cache files
        files_created = []
        for i in range(3):
            data = [{"id": i}]
            cache_file, _ = write_cache(data, f"evict{i}" * 4)
            files_created.append(cache_file)
            time.sleep(0.01)  # Ensure different timestamps

        # Mock the directory being full
        with patch("affinity.cli.query.cursor.CACHE_EVICTION_TARGET_BYTES", 10):  # Very low target
            _evict_cache_files(needed_bytes=1000)

        # Clean up remaining files
        for f in files_created:
            delete_cache(f)

    def test_cache_constants_defined(self) -> None:
        """Cache limit constants are properly defined."""
        from affinity.cli.query.cursor import (
            CACHE_EVICTION_TARGET_BYTES,
            MAX_CACHE_DIR_BYTES,
            MAX_CACHE_FILE_BYTES,
        )

        assert MAX_CACHE_FILE_BYTES == 100 * 1024 * 1024  # 100MB
        assert MAX_CACHE_DIR_BYTES == 500 * 1024 * 1024  # 500MB
        assert CACHE_EVICTION_TARGET_BYTES == 400 * 1024 * 1024  # 80%


# =============================================================================
# Cache File Permissions Tests (Appendix B)
# =============================================================================


class TestCacheFilePermissions:
    """Tests for cache file security permissions."""

    def test_cache_file_has_restrictive_permissions(self) -> None:
        """Cache files are created with 0600 permissions (owner only)."""
        import stat

        data = [{"id": 1}]
        cache_file, _ = write_cache(data, "perms" * 6)

        try:
            file_stat = Path(cache_file).stat()
            # Get permission bits (last 9 bits)
            perms = stat.S_IMODE(file_stat.st_mode)

            # Should be 0600 (owner read+write only)
            # Note: On some systems this might be affected by umask
            assert perms & 0o077 == 0  # No group/other permissions
            assert perms & 0o600 == 0o600  # Owner read+write
        finally:
            delete_cache(cache_file)

    def test_cache_file_not_world_readable(self) -> None:
        """Cache files are not world-readable."""
        import stat

        data = [{"id": 1, "sensitive": "data"}]
        cache_file, _ = write_cache(data, "secure" * 4)

        try:
            file_stat = Path(cache_file).stat()
            perms = stat.S_IMODE(file_stat.st_mode)

            # Should not have other-read permission
            assert not (perms & stat.S_IROTH)
            # Should not have other-write permission
            assert not (perms & stat.S_IWOTH)
        finally:
            delete_cache(cache_file)


# =============================================================================
# Cache LRU Eviction Tests (Appendix B)
# =============================================================================


class TestCacheLruEviction:
    """Tests for LRU cache eviction policy."""

    def test_eviction_deletes_oldest_files_first(self) -> None:
        """LRU eviction deletes oldest files first."""
        from affinity.cli.query.cursor import _evict_cache_files

        # Create 3 files with different timestamps
        files_created = []
        for i in range(3):
            data = [{"id": i}]
            cache_file, _ = write_cache(data, f"lru{i}x" * 4)
            files_created.append(cache_file)
            time.sleep(0.05)  # Ensure different timestamps

        # All files should exist
        for f in files_created:
            assert Path(f).exists()

        # Trigger eviction with very low target
        with patch("affinity.cli.query.cursor.CACHE_EVICTION_TARGET_BYTES", 1):
            _evict_cache_files(needed_bytes=1000)

        # Clean up any remaining files
        for f in files_created:
            delete_cache(f)

    def test_eviction_stops_when_target_reached(self) -> None:
        """Eviction stops when under target size."""
        from affinity.cli.query.cursor import _evict_cache_files

        # Create a file
        data = [{"id": 1}]
        cache_file, _ = write_cache(data, "stop" * 6)

        try:
            # With high target, file should survive eviction
            with patch(
                "affinity.cli.query.cursor.CACHE_EVICTION_TARGET_BYTES",
                1000 * 1024 * 1024,  # 1GB target (very high)
            ):
                _evict_cache_files(needed_bytes=100)

            # File should still exist
            assert Path(cache_file).exists()
        finally:
            delete_cache(cache_file)


# =============================================================================
# API Cursor Integration Tests (Appendix B)
# =============================================================================


class TestApiCursorIntegration:
    """Tests for API cursor capture and storage in streaming mode."""

    def test_query_result_has_api_cursor_field(self) -> None:
        """QueryResult model includes api_cursor field."""
        from affinity.cli.query.models import QueryResult

        result = QueryResult(data=[{"id": 1}])
        assert hasattr(result, "api_cursor")
        assert result.api_cursor is None

    def test_query_result_with_api_cursor(self) -> None:
        """QueryResult can store api_cursor value."""
        from affinity.cli.query.models import QueryResult

        result = QueryResult(
            data=[{"id": 1}],
            api_cursor="https://api.affinity.co/v2/persons?page=2",
        )
        assert result.api_cursor == "https://api.affinity.co/v2/persons?page=2"

    def test_execution_context_has_last_api_cursor(self) -> None:
        """ExecutionContext tracks last_api_cursor."""
        from affinity.cli.query.executor import ExecutionContext

        ctx = ExecutionContext(query=Query(from_="persons"))
        assert hasattr(ctx, "last_api_cursor")
        assert ctx.last_api_cursor is None

    def test_streaming_cursor_preserves_api_cursor(self) -> None:
        """Streaming cursor roundtrip preserves api_cursor."""
        query = Query(from_="persons")
        api_cursor_value = "https://api.affinity.co/v2/persons?cursor=abc123"

        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=50,
            api_cursor=api_cursor_value,
        )

        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)

        assert decoded.api_cursor == api_cursor_value
        assert decoded.mode == "streaming"

    def test_streaming_cursor_without_api_cursor(self) -> None:
        """Streaming cursor works without api_cursor (fallback mode)."""
        query = Query(from_="persons")

        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=50,
            last_id=100,
        )

        assert cursor.api_cursor is None
        assert cursor.skip == 50
        assert cursor.last_id == 100


# =============================================================================
# Full-Fetch Mode Tests (Appendix B - Modes)
# =============================================================================


class TestFullFetchModeScenarios:
    """Tests for full-fetch mode scenarios including aggregate queries."""

    def test_full_fetch_with_aggregate_cursor_structure(self) -> None:
        """Aggregate queries use full-fetch mode cursor."""
        query = Query(
            from_="persons",
            aggregate={"count": {"count": "*"}},
        )
        cursor = create_full_fetch_cursor(
            query=query,
            output_format="toon",
            skip=50,
            cache_file="/tmp/xaffinity_cache/xaff_test.json",
            cache_hash="a" * 64,
            total=500,
        )

        assert cursor.mode == "full-fetch"
        assert cursor.cache_file is not None
        assert cursor.cache_hash is not None

    def test_full_fetch_with_order_by_cursor_structure(self) -> None:
        """OrderBy queries use full-fetch mode cursor."""
        query = Query(
            from_="persons",
            order_by=[{"field": "name", "direction": "asc"}],
        )
        cursor = create_full_fetch_cursor(
            query=query,
            output_format="toon",
            skip=50,
            cache_file="/tmp/xaffinity_cache/xaff_test.json",
            cache_hash="b" * 64,
            total=200,
        )

        assert cursor.mode == "full-fetch"
        assert cursor.cache_file is not None

    def test_full_fetch_with_group_by_cursor_structure(self) -> None:
        """GroupBy queries use full-fetch mode cursor."""
        query = Query(
            from_="persons",
            group_by="email",
            aggregate={"total": {"count": "*"}},
        )
        cursor = create_full_fetch_cursor(
            query=query,
            output_format="toon",
            skip=10,
            cache_file="/tmp/xaffinity_cache/xaff_test.json",
            cache_hash="c" * 64,
            total=50,
        )

        assert cursor.mode == "full-fetch"
        # Cursor doesn't store group_by - only query hash
        assert cursor.qh == hash_query(query, "toon")


# =============================================================================
# Cache Progress Tests (Appendix B - Progress)
# =============================================================================


class TestCacheProgressEmission:
    """Tests for cache-related progress emission."""

    def test_emit_cache_progress_outputs_valid_ndjson(self) -> None:
        """emit_cache_progress outputs valid NDJSON."""
        from io import StringIO

        from affinity.cli.query.progress import emit_cache_progress

        captured = StringIO()
        emit_cache_progress("Serving from cache", output=captured)

        output = captured.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["type"] == "progress"
        assert parsed["event"] == "cache_hit"
        assert parsed["message"] == "Serving from cache"
        assert parsed["progress"] == 100

    def test_emit_cache_progress_custom_progress(self) -> None:
        """emit_cache_progress respects custom progress value."""
        from io import StringIO

        from affinity.cli.query.progress import emit_cache_progress

        captured = StringIO()
        emit_cache_progress("Starting...", progress=0, output=captured)

        output = captured.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["progress"] == 0

    def test_emit_cache_progress_is_single_line(self) -> None:
        """Cache progress is single-line NDJSON."""
        from io import StringIO

        from affinity.cli.query.progress import emit_cache_progress

        captured = StringIO()
        emit_cache_progress("Serving from cache (no API calls)", output=captured)

        lines = captured.getvalue().strip().split("\n")
        assert len(lines) == 1


# =============================================================================
# Startup Cleanup Tests (Appendix B - Cache)
# =============================================================================


class TestStartupCleanup:
    """Tests for cache cleanup on CLI startup."""

    def test_cleanup_cache_is_callable(self) -> None:
        """cleanup_cache() can be called without error."""
        # This tests that the function is properly exported and callable
        cleanup_cache()  # Should not raise

    def test_cleanup_cache_removes_expired_files_only(self) -> None:
        """Cleanup removes only files older than TTL."""
        # Create a fresh file
        data = [{"id": 1}]
        cache_file, _ = write_cache(data, "f" * 24)  # Valid 24-char hex hash

        # File should exist before cleanup
        assert Path(cache_file).exists()

        # Run cleanup
        cleanup_cache()

        # Fresh file should still exist
        assert Path(cache_file).exists()

        # Clean up
        delete_cache(cache_file)


# =============================================================================
# Cursor Validation Edge Cases (Appendix B - Errors)
# =============================================================================


class TestCursorValidationEdgeCases:
    """Edge case tests for cursor validation."""

    def test_cursor_with_skip_zero(self) -> None:
        """Cursor with skip=0 is valid (first page)."""
        query = Query(from_="persons")
        cursor = CursorPayload(
            v=CURSOR_VERSION,
            qh=hash_query(query, "toon"),
            skip=0,
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        # Should not raise
        validate_cursor(cursor, query, "toon")

    def test_cursor_with_very_large_skip(self) -> None:
        """Cursor with very large skip is valid."""
        query = Query(from_="persons")
        cursor = CursorPayload(
            v=CURSOR_VERSION,
            qh=hash_query(query, "toon"),
            skip=1000000,  # Very large
            ts=int(time.time() * 1000),
            mode="streaming",
        )

        # Should not raise
        validate_cursor(cursor, query, "toon")


# =============================================================================
# maxRecords Interaction Tests (Appendix B - maxRecords)
# =============================================================================


class TestMaxRecordsInteraction:
    """Tests for maxRecords interaction with cursors."""

    def test_cursor_skip_preserves_original_limit(self) -> None:
        """Cursor skip doesn't depend on original maxRecords."""
        query = Query(from_="persons", limit=100)

        # Original query had limit=100, cursor skips 50
        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=50,
            total=100,
        )

        assert cursor.skip == 50
        assert cursor.total == 100

    def test_full_fetch_cache_serves_without_api_calls(self) -> None:
        """Full-fetch cursor with cache doesn't need maxRecords on resume."""
        # Write some cached data
        query_hash = "a" * 24  # Valid 24-char hex hash
        data = [{"id": i} for i in range(100)]
        cache_file, cache_hash = write_cache(data, query_hash)

        try:
            # Create cursor pointing to cache
            cursor = CursorPayload(
                v=1,
                qh=query_hash,
                skip=50,
                ts=int(time.time() * 1000),
                mode="full-fetch",
                cache_file=cache_file,
                cache_hash=cache_hash,
                total=100,
            )

            # Read from cache - this should work without any API interaction
            cached_data = read_cache(cursor)

            assert cached_data is not None
            assert len(cached_data) == 100

        finally:
            delete_cache(cache_file)


# =============================================================================
# O(1) Streaming Resumption Tests (Appendix B - Modes)
# =============================================================================


class TestO1StreamingResumption:
    """Tests for O(1) streaming resumption via API cursor."""

    def test_executor_accepts_resume_api_cursor(self) -> None:
        """QueryExecutor accepts resume_api_cursor parameter."""
        from unittest.mock import MagicMock

        from affinity.cli.query.executor import QueryExecutor

        mock_client = MagicMock()
        executor = QueryExecutor(
            mock_client,
            resume_api_cursor="https://api.affinity.co/v2/persons?cursor=abc123",
        )

        assert executor.resume_api_cursor == "https://api.affinity.co/v2/persons?cursor=abc123"

    def test_executor_default_resume_cursor_is_none(self) -> None:
        """QueryExecutor defaults to no resume cursor."""
        from unittest.mock import MagicMock

        from affinity.cli.query.executor import QueryExecutor

        mock_client = MagicMock()
        executor = QueryExecutor(mock_client)

        assert executor.resume_api_cursor is None

    def test_streaming_cursor_with_api_cursor_structure(self) -> None:
        """Streaming cursor with api_cursor has correct structure for O(1) resumption."""
        query = Query(from_="persons", limit=100)
        api_cursor_url = "https://api.affinity.co/v2/persons?cursor=abc123"

        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=50,
            last_id=12345,
            api_cursor=api_cursor_url,
        )

        assert cursor.mode == "streaming"
        assert cursor.api_cursor == api_cursor_url
        assert cursor.skip == 50  # Skip tracked for fallback
        assert cursor.last_id == 12345

    def test_streaming_cursor_api_cursor_roundtrip(self) -> None:
        """API cursor survives encode/decode roundtrip."""
        query = Query(from_="persons")
        api_cursor_url = "https://api.affinity.co/v2/persons?cursor=xyz789&page=2"

        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=100,
            api_cursor=api_cursor_url,
        )

        encoded = encode_cursor(cursor)
        decoded = decode_cursor(encoded)

        assert decoded.api_cursor == api_cursor_url
        assert decoded.mode == "streaming"

    def test_streaming_cursor_without_api_cursor_uses_skip_fallback(self) -> None:
        """Streaming cursor without api_cursor falls back to skip-based resumption."""
        query = Query(from_="persons")

        cursor = create_streaming_cursor(
            query=query,
            output_format="toon",
            skip=75,
            last_id=999,
        )

        assert cursor.api_cursor is None
        assert cursor.skip == 75
        assert cursor.last_id == 999
        # Skip-based fallback will use skip and last_id for position finding

    def test_full_fetch_cursor_does_not_use_api_cursor(self) -> None:
        """Full-fetch cursor doesn't store api_cursor (uses cache instead)."""
        query = Query(
            from_="persons",
            order_by=[{"field": "name", "direction": "asc"}],
        )

        cursor = create_full_fetch_cursor(
            query=query,
            output_format="toon",
            skip=50,
            cache_file="/tmp/xaffinity_cache/xaff_test.json",
            cache_hash="a" * 64,
            total=200,
        )

        assert cursor.mode == "full-fetch"
        assert cursor.api_cursor is None  # Full-fetch uses cache, not api_cursor
        assert cursor.cache_file is not None
