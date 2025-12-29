"""Unit tests for CLI serialization helpers."""

import json
from datetime import datetime, timezone

from affinity.cli.serialization import serialize_model_for_cli, serialize_models_for_cli
from affinity.models.entities import ListEntry, Person


class TestSerializeModelForCli:
    """Test serialize_model_for_cli function."""

    def test_serializes_person_with_aliases(self):
        """Verify model is serialized with field aliases (camelCase)."""
        person = Person(
            id=123,
            first_name="John",
            last_name="Doe",
            emails=["john@example.com"],
        )

        result = serialize_model_for_cli(person)

        # Should use camelCase aliases
        assert result["id"] == 123
        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"
        assert result["emailAddresses"] == ["john@example.com"]

        # Should not include snake_case names
        assert "first_name" not in result
        assert "last_name" not in result
        assert "emails" not in result  # Field uses alias "emailAddresses"

    def test_serializes_datetime_as_iso_string(self):
        """Verify datetime fields are converted to ISO strings."""
        entry = ListEntry(
            id=456,
            list_id=789,
            creator_id=101,
            entity_id=202,
            created_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )

        result = serialize_model_for_cli(entry)

        # created_at should be serialized as ISO string
        assert isinstance(result["createdAt"], str)
        assert result["createdAt"] == "2025-01-15T10:30:00Z"

        # Should be JSON-serializable (would fail if datetime wasn't converted)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["createdAt"] == "2025-01-15T10:30:00Z"

    def test_excludes_none_values(self):
        """Verify None values are excluded from output."""
        person = Person(
            id=123,
            first_name="John",
            last_name="Doe",
            emails=["john@example.com"],
            # primary_email_id and other optional fields are None
        )

        result = serialize_model_for_cli(person)

        # None values should be excluded
        assert "primaryEmailId" not in result
        assert "primary_email_id" not in result

        # Non-None values should be included
        assert "id" in result
        assert "firstName" in result

    def test_output_is_json_safe(self):
        """Verify output contains only JSON-safe types."""
        entry = ListEntry(
            id=123,
            list_id=456,
            creator_id=789,
            entity_id=999,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        result = serialize_model_for_cli(entry)

        # Should be fully JSON-serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        # Verify all values are JSON-safe types
        def verify_json_safe(data):
            if isinstance(data, dict):
                for value in data.values():
                    verify_json_safe(value)
            elif isinstance(data, list):
                for item in data:
                    verify_json_safe(item)
            else:
                assert isinstance(data, (str, int, float, bool, type(None)))

        verify_json_safe(parsed)


class TestSerializeModelsForCli:
    """Test serialize_models_for_cli function."""

    def test_serializes_list_of_models(self):
        """Verify list of models is serialized correctly."""
        people = [
            Person(id=1, first_name="Alice", last_name="Smith", emails=[]),
            Person(id=2, first_name="Bob", last_name="Jones", emails=[]),
            Person(id=3, first_name="Carol", last_name="White", emails=[]),
        ]

        result = serialize_models_for_cli(people)

        assert len(result) == 3
        assert result[0]["id"] == 1
        assert result[0]["firstName"] == "Alice"
        assert result[1]["id"] == 2
        assert result[1]["firstName"] == "Bob"
        assert result[2]["id"] == 3
        assert result[2]["firstName"] == "Carol"

    def test_serializes_empty_list(self):
        """Verify empty list is handled correctly."""
        result = serialize_models_for_cli([])
        assert result == []

    def test_serializes_models_with_datetime(self):
        """Verify models with datetime fields are serialized correctly."""
        entries = [
            ListEntry(
                id=1,
                list_id=100,
                creator_id=200,
                entity_id=300,
                created_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            ),
            ListEntry(
                id=2,
                list_id=100,
                creator_id=200,
                entity_id=400,
                created_at=datetime(2025, 1, 2, 11, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        result = serialize_models_for_cli(entries)

        assert len(result) == 2
        assert isinstance(result[0]["createdAt"], str)
        assert isinstance(result[1]["createdAt"], str)
        assert result[0]["createdAt"] == "2025-01-01T10:00:00Z"
        assert result[1]["createdAt"] == "2025-01-02T11:00:00Z"

    def test_output_is_json_serializable(self):
        """Verify entire output list is JSON-serializable."""
        people = [
            Person(id=1, first_name="Alice", last_name="Smith", emails=[]),
            Person(id=2, first_name="Bob", last_name="Jones", emails=[]),
        ]

        result = serialize_models_for_cli(people)

        # Should be fully JSON-serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        assert len(parsed) == 2
        assert parsed[0]["firstName"] == "Alice"
        assert parsed[1]["firstName"] == "Bob"
