"""Tests for unreplied email detection functionality.

Tests the check_unreplied_email function and --check-unreplied-emails CLI flag.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from affinity.cli.interaction_utils import (
    UNREPLIED_EMAIL_CSV_COLUMNS,
    check_unreplied_email,
    flatten_unreplied_email_for_csv,
)


class TestCheckUnrepliedEmail:
    """Tests for check_unreplied_email function."""

    def test_returns_none_when_no_emails(self) -> None:
        """Should return None when entity has no email interactions."""
        mock_client = MagicMock()
        mock_client.interactions.iter.return_value = iter([])

        result = check_unreplied_email(
            client=mock_client,
            entity_type="company",
            entity_id=123,
            lookback_days=30,
        )

        assert result is None

    def test_returns_none_when_no_incoming_emails(self) -> None:
        """Should return None when all emails are outgoing."""
        from affinity.models.types import InteractionDirection

        mock_email = MagicMock()
        mock_email.date = datetime.now(timezone.utc) - timedelta(days=1)
        mock_email.direction = InteractionDirection.OUTGOING
        mock_email.subject = "Re: Hello"

        mock_client = MagicMock()
        mock_client.interactions.iter.return_value = iter([mock_email])

        result = check_unreplied_email(
            client=mock_client,
            entity_type="company",
            entity_id=123,
            lookback_days=30,
        )

        assert result is None

    def test_returns_none_when_incoming_has_reply(self) -> None:
        """Should return None when last incoming email has a reply."""
        from affinity.models.types import InteractionDirection

        # Incoming email 2 days ago
        incoming = MagicMock()
        incoming.date = datetime.now(timezone.utc) - timedelta(days=2)
        incoming.direction = InteractionDirection.INCOMING
        incoming.subject = "Question"

        # Outgoing reply 1 day ago
        reply = MagicMock()
        reply.date = datetime.now(timezone.utc) - timedelta(days=1)
        reply.direction = InteractionDirection.OUTGOING
        reply.subject = "Re: Question"

        mock_client = MagicMock()
        mock_client.interactions.iter.return_value = iter([incoming, reply])

        result = check_unreplied_email(
            client=mock_client,
            entity_type="person",
            entity_id=456,
            lookback_days=30,
        )

        assert result is None

    def test_returns_unreplied_email_when_no_reply(self) -> None:
        """Should return unreplied email info when no reply exists."""
        from affinity.models.types import InteractionDirection

        # Incoming email 2 days ago - no reply
        incoming = MagicMock()
        email_date = datetime.now(timezone.utc) - timedelta(days=2)
        incoming.date = email_date
        incoming.direction = InteractionDirection.INCOMING
        incoming.subject = "Urgent: Need response"

        mock_client = MagicMock()
        mock_client.interactions.iter.return_value = iter([incoming])

        result = check_unreplied_email(
            client=mock_client,
            entity_type="company",
            entity_id=123,
            lookback_days=30,
        )

        assert result is not None
        assert "date" in result
        assert result["daysSince"] == 2
        assert result["subject"] == "Urgent: Need response"

    def test_finds_most_recent_unreplied_incoming(self) -> None:
        """Should find the most recent incoming email without a reply."""
        from affinity.models.types import InteractionDirection

        # Older incoming (3 days ago)
        older_incoming = MagicMock()
        older_incoming.date = datetime.now(timezone.utc) - timedelta(days=3)
        older_incoming.direction = InteractionDirection.INCOMING
        older_incoming.subject = "Old email"

        # Newer incoming (1 day ago) - most recent
        newer_incoming = MagicMock()
        newer_date = datetime.now(timezone.utc) - timedelta(days=1)
        newer_incoming.date = newer_date
        newer_incoming.direction = InteractionDirection.INCOMING
        newer_incoming.subject = "New email"

        mock_client = MagicMock()
        mock_client.interactions.iter.return_value = iter([older_incoming, newer_incoming])

        result = check_unreplied_email(
            client=mock_client,
            entity_type="person",
            entity_id=789,
            lookback_days=30,
        )

        assert result is not None
        assert result["daysSince"] == 1
        assert result["subject"] == "New email"

    def test_handles_unsupported_entity_type(self) -> None:
        """Should return None for unsupported entity types."""
        mock_client = MagicMock()

        result = check_unreplied_email(
            client=mock_client,
            entity_type="opportunity",
            entity_id=123,
            lookback_days=30,
        )

        assert result is None
        # Should not have called the interactions API
        mock_client.interactions.iter.assert_not_called()

    def test_handles_api_error_gracefully(self) -> None:
        """Should return None and log warning on API error."""
        mock_client = MagicMock()
        mock_client.interactions.iter.side_effect = Exception("API error")

        result = check_unreplied_email(
            client=mock_client,
            entity_type="company",
            entity_id=123,
            lookback_days=30,
        )

        assert result is None


class TestFlattenUnrepliedEmailForCsv:
    """Tests for flatten_unreplied_email_for_csv function."""

    def test_returns_all_columns_empty_when_none(self) -> None:
        """Should return all columns with empty strings when input is None."""
        result = flatten_unreplied_email_for_csv(None)

        assert len(result) == len(UNREPLIED_EMAIL_CSV_COLUMNS)
        for col in UNREPLIED_EMAIL_CSV_COLUMNS:
            assert col in result
            assert result[col] == ""

    def test_returns_all_columns_empty_when_empty_dict(self) -> None:
        """Should return all columns with empty strings for empty dict."""
        result = flatten_unreplied_email_for_csv({})

        assert len(result) == len(UNREPLIED_EMAIL_CSV_COLUMNS)
        for col in UNREPLIED_EMAIL_CSV_COLUMNS:
            assert result[col] == ""

    def test_flattens_unreplied_email_data(self) -> None:
        """Should flatten unreplied email data correctly."""
        unreplied_data = {
            "date": "2026-01-10T10:00:00+00:00",
            "daysSince": 5,
            "subject": "Need response",
        }

        result = flatten_unreplied_email_for_csv(unreplied_data)

        assert result["unrepliedEmailDate"] == "2026-01-10T10:00:00+00:00"
        assert result["unrepliedEmailDaysSince"] == "5"
        assert result["unrepliedEmailSubject"] == "Need response"

    def test_handles_missing_subject(self) -> None:
        """Should handle missing subject gracefully."""
        unreplied_data = {
            "date": "2026-01-10T10:00:00+00:00",
            "daysSince": 5,
            "subject": None,
        }

        result = flatten_unreplied_email_for_csv(unreplied_data)

        assert result["unrepliedEmailSubject"] == ""

    def test_handles_days_since_zero(self) -> None:
        """Should handle daysSince=0 correctly."""
        unreplied_data = {
            "date": "2026-01-17T10:00:00+00:00",
            "daysSince": 0,
            "subject": "Today's email",
        }

        result = flatten_unreplied_email_for_csv(unreplied_data)

        assert result["unrepliedEmailDaysSince"] == "0"


class TestUnrepliedEmailCsvColumns:
    """Tests for UNREPLIED_EMAIL_CSV_COLUMNS constant."""

    def test_has_expected_columns(self) -> None:
        """Should have all expected columns."""
        expected = [
            "unrepliedEmailDate",
            "unrepliedEmailDaysSince",
            "unrepliedEmailSubject",
        ]
        assert expected == UNREPLIED_EMAIL_CSV_COLUMNS

    def test_has_three_columns(self) -> None:
        """Should have exactly 3 columns."""
        assert len(UNREPLIED_EMAIL_CSV_COLUMNS) == 3
