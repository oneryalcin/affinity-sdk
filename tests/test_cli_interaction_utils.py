"""Unit tests for interaction_utils.py.

Tests the transform and flatten functions used by list export --expand interactions
and query expand: ["interactionDates"].
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from affinity.cli.interaction_utils import (
    INTERACTION_CSV_COLUMNS,
    flatten_interactions_for_csv,
    transform_interaction_data,
)


class TestTransformInteractionData:
    """Tests for transform_interaction_data function."""

    def test_returns_none_when_interaction_dates_is_none(self) -> None:
        """Test that None is returned when interaction_dates is None."""
        result = transform_interaction_data(None, None)
        assert result is None

    def test_transforms_last_meeting(self) -> None:
        """Test transformation of last meeting (last_event) data."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_event_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        )

        with patch("affinity.cli.interaction_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = transform_interaction_data(interaction_dates, None)

        assert result is not None
        assert "lastMeeting" in result
        assert result["lastMeeting"]["date"] == "2026-01-10T10:00:00+00:00"
        assert result["lastMeeting"]["daysSince"] == 5

    def test_transforms_next_meeting(self) -> None:
        """Test transformation of next meeting (next_event) data."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            next_event_date=datetime(2026, 1, 25, 14, 0, 0, tzinfo=timezone.utc),
        )

        with patch("affinity.cli.interaction_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = transform_interaction_data(interaction_dates, None)

        assert result is not None
        assert "nextMeeting" in result
        assert result["nextMeeting"]["date"] == "2026-01-25T14:00:00+00:00"
        assert result["nextMeeting"]["daysUntil"] == 10

    def test_transforms_last_email(self) -> None:
        """Test transformation of last email data."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_email_date=datetime(2026, 1, 12, 9, 30, 0, tzinfo=timezone.utc),
        )

        with patch("affinity.cli.interaction_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = transform_interaction_data(interaction_dates, None)

        assert result is not None
        assert "lastEmail" in result
        assert result["lastEmail"]["date"] == "2026-01-12T09:30:00+00:00"
        assert result["lastEmail"]["daysSince"] == 3

    def test_transforms_last_interaction(self) -> None:
        """Test transformation of last interaction data."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_interaction_date=datetime(2026, 1, 14, 15, 0, 0, tzinfo=timezone.utc),
        )

        with patch("affinity.cli.interaction_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = transform_interaction_data(interaction_dates, None)

        assert result is not None
        assert "lastInteraction" in result
        assert result["lastInteraction"]["date"] == "2026-01-14T15:00:00+00:00"
        assert result["lastInteraction"]["daysSince"] == 0  # Same day

    def test_includes_team_member_ids_from_interactions_dict(self) -> None:
        """Test that team member IDs are extracted from interactions dict."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_event_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        )
        interactions: dict[str, Any] = {
            "last_event": {"person_ids": [101, 102, 103]},
        }

        result = transform_interaction_data(interaction_dates, interactions)

        assert result is not None
        assert "lastMeeting" in result
        assert result["lastMeeting"]["teamMemberIds"] == [101, 102, 103]

    def test_resolves_person_names_when_client_provided(self) -> None:
        """Test that person names are resolved when client is provided."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_event_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        )
        interactions: dict[str, Any] = {
            "last_event": {"person_ids": [101, 102]},
        }

        # Mock client and person responses
        mock_client = MagicMock()
        mock_person_1 = MagicMock()
        mock_person_1.full_name = "Alice Smith"
        mock_person_2 = MagicMock()
        mock_person_2.full_name = "Bob Jones"
        mock_client.persons.get.side_effect = [mock_person_1, mock_person_2]

        result = transform_interaction_data(interaction_dates, interactions, client=mock_client)

        assert result is not None
        assert "lastMeeting" in result
        assert result["lastMeeting"]["teamMemberNames"] == ["Alice Smith", "Bob Jones"]

    def test_uses_person_name_cache(self) -> None:
        """Test that person name cache is used to avoid duplicate lookups."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_event_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        )
        interactions: dict[str, Any] = {
            "last_event": {"person_ids": [101, 102]},
        }

        mock_client = MagicMock()
        mock_person = MagicMock()
        mock_person.full_name = "New Person"
        mock_client.persons.get.return_value = mock_person

        # Pre-populate cache
        cache: dict[int, str] = {101: "Cached Alice"}

        result = transform_interaction_data(
            interaction_dates, interactions, client=mock_client, person_name_cache=cache
        )

        assert result is not None
        assert result["lastMeeting"]["teamMemberNames"] == ["Cached Alice", "New Person"]
        # Only one API call made (for person 102, 101 was cached)
        assert mock_client.persons.get.call_count == 1

    def test_returns_empty_dict_when_no_dates(self) -> None:
        """Test that None is returned when InteractionDates has no dates."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates()  # All fields None

        result = transform_interaction_data(interaction_dates, None)

        assert result is None

    def test_all_dates_combined(self) -> None:
        """Test transformation with all date types present."""
        from affinity.models.entities import InteractionDates

        interaction_dates = InteractionDates(
            last_event_date=datetime(2026, 1, 5, 10, 0, 0, tzinfo=timezone.utc),
            next_event_date=datetime(2026, 1, 20, 14, 0, 0, tzinfo=timezone.utc),
            last_email_date=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
            last_interaction_date=datetime(2026, 1, 10, 15, 0, 0, tzinfo=timezone.utc),
        )

        with patch("affinity.cli.interaction_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = transform_interaction_data(interaction_dates, None)

        assert result is not None
        assert "lastMeeting" in result
        assert "nextMeeting" in result
        assert "lastEmail" in result
        assert "lastInteraction" in result


class TestFlattenInteractionsForCsv:
    """Tests for flatten_interactions_for_csv function."""

    def test_returns_all_columns_with_empty_strings_when_none(self) -> None:
        """Test that all columns are returned with empty strings when input is None."""
        result = flatten_interactions_for_csv(None)

        assert len(result) == len(INTERACTION_CSV_COLUMNS)
        for col in INTERACTION_CSV_COLUMNS:
            assert col in result
            assert result[col] == ""

    def test_returns_all_columns_with_empty_strings_when_empty_dict(self) -> None:
        """Test that all columns are returned with empty strings for empty dict."""
        result = flatten_interactions_for_csv({})

        assert len(result) == len(INTERACTION_CSV_COLUMNS)
        for col in INTERACTION_CSV_COLUMNS:
            assert result[col] == ""

    def test_flattens_last_meeting(self) -> None:
        """Test flattening of lastMeeting data."""
        interactions = {
            "lastMeeting": {
                "date": "2026-01-10T10:00:00Z",
                "daysSince": 5,
                "teamMemberNames": ["Alice", "Bob"],
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["lastMeetingDate"] == "2026-01-10T10:00:00Z"
        assert result["lastMeetingDaysSince"] == "5"
        assert result["lastMeetingTeamMembers"] == "Alice, Bob"

    def test_flattens_next_meeting(self) -> None:
        """Test flattening of nextMeeting data."""
        interactions = {
            "nextMeeting": {
                "date": "2026-01-25T14:00:00Z",
                "daysUntil": 10,
                "teamMemberNames": ["Carol"],
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["nextMeetingDate"] == "2026-01-25T14:00:00Z"
        assert result["nextMeetingDaysUntil"] == "10"
        assert result["nextMeetingTeamMembers"] == "Carol"

    def test_flattens_last_email(self) -> None:
        """Test flattening of lastEmail data."""
        interactions = {
            "lastEmail": {
                "date": "2026-01-12T09:30:00Z",
                "daysSince": 3,
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["lastEmailDate"] == "2026-01-12T09:30:00Z"
        assert result["lastEmailDaysSince"] == "3"

    def test_flattens_last_interaction(self) -> None:
        """Test flattening of lastInteraction data."""
        interactions = {
            "lastInteraction": {
                "date": "2026-01-14T15:00:00Z",
                "daysSince": 1,
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["lastInteractionDate"] == "2026-01-14T15:00:00Z"
        assert result["lastInteractionDaysSince"] == "1"

    def test_handles_missing_team_members(self) -> None:
        """Test handling when teamMemberNames is missing."""
        interactions = {
            "lastMeeting": {
                "date": "2026-01-10T10:00:00Z",
                "daysSince": 5,
                # No teamMemberNames
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["lastMeetingTeamMembers"] == ""

    def test_handles_empty_team_members(self) -> None:
        """Test handling when teamMemberNames is empty list."""
        interactions = {
            "lastMeeting": {
                "date": "2026-01-10T10:00:00Z",
                "daysSince": 5,
                "teamMemberNames": [],
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["lastMeetingTeamMembers"] == ""

    def test_handles_days_since_zero(self) -> None:
        """Test that daysSince=0 is properly converted to string."""
        interactions = {
            "lastMeeting": {
                "date": "2026-01-15T10:00:00Z",
                "daysSince": 0,
            }
        }

        result = flatten_interactions_for_csv(interactions)

        assert result["lastMeetingDaysSince"] == "0"


class TestInteractionCsvColumns:
    """Tests for INTERACTION_CSV_COLUMNS constant."""

    def test_has_expected_columns(self) -> None:
        """Test that all expected columns are present."""
        expected = [
            "lastMeetingDate",
            "lastMeetingDaysSince",
            "lastMeetingTeamMembers",
            "nextMeetingDate",
            "nextMeetingDaysUntil",
            "nextMeetingTeamMembers",
            "lastEmailDate",
            "lastEmailDaysSince",
            "lastInteractionDate",
            "lastInteractionDaysSince",
        ]
        assert expected == INTERACTION_CSV_COLUMNS

    def test_has_ten_columns(self) -> None:
        """Test that there are exactly 10 columns."""
        assert len(INTERACTION_CSV_COLUMNS) == 10
