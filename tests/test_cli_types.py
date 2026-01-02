"""Tests for CLI type definitions and validation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from affinity.cli.types import validate_json_serializable


class TestValidateJsonSerializable:
    """Tests for validate_json_serializable function."""

    def test_valid_string(self) -> None:
        """String is JSON-serializable."""
        validate_json_serializable("hello")

    def test_valid_int(self) -> None:
        """Integer is JSON-serializable."""
        validate_json_serializable(42)

    def test_valid_float(self) -> None:
        """Float is JSON-serializable."""
        validate_json_serializable(3.14)

    def test_valid_bool(self) -> None:
        """Boolean is JSON-serializable."""
        validate_json_serializable(True)
        validate_json_serializable(False)

    def test_valid_none(self) -> None:
        """None is JSON-serializable."""
        validate_json_serializable(None)

    def test_valid_empty_dict(self) -> None:
        """Empty dict is JSON-serializable."""
        validate_json_serializable({})

    def test_valid_simple_dict(self) -> None:
        """Simple dict with primitives is JSON-serializable."""
        validate_json_serializable({"id": 123, "name": "John", "active": True})

    def test_valid_nested_dict(self) -> None:
        """Nested dict is JSON-serializable."""
        validate_json_serializable(
            {
                "user": {
                    "id": 1,
                    "profile": {
                        "name": "Alice",
                        "score": 99.5,
                    },
                }
            }
        )

    def test_valid_empty_list(self) -> None:
        """Empty list is JSON-serializable."""
        validate_json_serializable([])

    def test_valid_simple_list(self) -> None:
        """Simple list with primitives is JSON-serializable."""
        validate_json_serializable([1, 2, 3, "four", None, True])

    def test_valid_nested_list(self) -> None:
        """Nested list is JSON-serializable."""
        validate_json_serializable([[1, 2], [3, 4], [5, 6]])

    def test_valid_mixed_structure(self) -> None:
        """Complex nested structure is JSON-serializable."""
        validate_json_serializable(
            {
                "users": [
                    {"id": 1, "name": "Alice", "tags": ["admin", "active"]},
                    {"id": 2, "name": "Bob", "tags": []},
                ],
                "metadata": {
                    "count": 2,
                    "page": None,
                },
            }
        )

    def test_invalid_datetime(self) -> None:
        """datetime is not JSON-serializable."""
        with pytest.raises(TypeError, match="Non-JSON-serializable type at root: datetime"):
            validate_json_serializable(datetime.now())

    def test_invalid_uuid(self) -> None:
        """UUID is not JSON-serializable."""
        with pytest.raises(TypeError, match="Non-JSON-serializable type at root: UUID"):
            validate_json_serializable(UUID("12345678-1234-5678-1234-567812345678"))

    def test_invalid_nested_in_dict(self) -> None:
        """Non-serializable type nested in dict raises with path."""
        with pytest.raises(
            TypeError, match=r"Non-JSON-serializable type at root\.created: datetime"
        ):
            validate_json_serializable({"id": 1, "created": datetime.now()})

    def test_invalid_deeply_nested_in_dict(self) -> None:
        """Non-serializable type deeply nested in dict raises with full path."""
        with pytest.raises(
            TypeError,
            match=r"Non-JSON-serializable type at root\.user\.profile\.timestamp: datetime",
        ):
            validate_json_serializable({"user": {"profile": {"timestamp": datetime.now()}}})

    def test_invalid_nested_in_list(self) -> None:
        """Non-serializable type in list raises with index."""
        with pytest.raises(TypeError, match=r"Non-JSON-serializable type at root\[1\]: datetime"):
            validate_json_serializable(["ok", datetime.now(), "also_ok"])

    def test_invalid_in_list_of_dicts(self) -> None:
        """Non-serializable type in list of dicts raises with full path."""
        with pytest.raises(
            TypeError, match=r"Non-JSON-serializable type at root\[0\]\.bad: datetime"
        ):
            validate_json_serializable([{"bad": datetime.now()}])

    def test_invalid_custom_object(self) -> None:
        """Custom objects are not JSON-serializable."""

        class CustomClass:
            pass

        with pytest.raises(TypeError, match="Non-JSON-serializable type at root: CustomClass"):
            validate_json_serializable(CustomClass())

    def test_invalid_bytes(self) -> None:
        """bytes is not JSON-serializable."""
        with pytest.raises(TypeError, match="Non-JSON-serializable type at root: bytes"):
            validate_json_serializable(b"hello")

    def test_invalid_set(self) -> None:
        """set is not JSON-serializable."""
        with pytest.raises(TypeError, match="Non-JSON-serializable type at root: set"):
            validate_json_serializable({1, 2, 3})

    def test_invalid_tuple(self) -> None:
        """tuple is not JSON-serializable (use list instead)."""
        with pytest.raises(TypeError, match="Non-JSON-serializable type at root: tuple"):
            validate_json_serializable((1, 2, 3))

    def test_custom_path(self) -> None:
        """Custom path prefix is used in error messages."""
        with pytest.raises(
            TypeError, match=r"Non-JSON-serializable type at response\.data\.value: datetime"
        ):
            validate_json_serializable({"value": datetime.now()}, path="response.data")
