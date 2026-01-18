"""Utilities for transforming and formatting interaction date data.

Supports `--expand interactions` for list export command.
This module provides:
- Transform functions to convert raw API data to a consistent shape
- CSV column definitions and flattening for export
- Person name resolution caching
- Unreplied email detection
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from affinity import Affinity, AsyncAffinity
    from affinity.models.entities import InteractionDates

logger = logging.getLogger(__name__)

# =============================================================================
# CSV Column Definitions
# =============================================================================

# Column names for flat CSV mode (order matters - must match flatten_interactions_for_csv)
INTERACTION_CSV_COLUMNS: list[str] = [
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

# Additional columns when --check-unreplied-emails is used
UNREPLIED_EMAIL_CSV_COLUMNS: list[str] = [
    "unrepliedEmailDate",
    "unrepliedEmailDaysSince",
    "unrepliedEmailSubject",
]


# =============================================================================
# Transform Functions
# =============================================================================


def transform_interaction_data(
    interaction_dates: InteractionDates | None,
    interactions: dict[str, Any] | None,
    *,
    client: Affinity | None = None,
    person_name_cache: dict[int, str] | None = None,
) -> dict[str, Any] | None:
    """Transform raw interaction date data into a structured dict.

    Combines data from both `interaction_dates` (date values) and `interactions`
    (detailed data with person_ids) into a unified structure suitable for
    JSON output and CSV flattening.

    Args:
        interaction_dates: Parsed InteractionDates object from entity
        interactions: Raw interactions dict from V1 API response
        client: Optional Affinity client for resolving person IDs to names
        person_name_cache: Optional cache dict for resolved person names.
            Will be mutated to store resolved names. Thread-safe under CPython GIL.

    Returns:
        Transformed dict with structured interaction data, or None if no data.

    Example output:
        {
            "lastMeeting": {
                "date": "2026-01-10T10:00:00Z",
                "daysSince": 7,
                "teamMemberIds": [1, 2],
                "teamMemberNames": ["John Doe", "Jane Smith"],
            },
            "nextMeeting": { ... },
            "lastEmail": { ... },
            "lastInteraction": { ... },
        }
    """
    if interaction_dates is None:
        return None

    now = datetime.now(timezone.utc)
    result: dict[str, Any] = {}

    # Last meeting (last_event)
    if interaction_dates.last_event_date:
        meeting_data: dict[str, Any] = {
            "date": _format_datetime(interaction_dates.last_event_date),
            "daysSince": _days_since(interaction_dates.last_event_date, now),
        }
        # Add team member data from interactions dict
        if interactions and "last_event" in interactions:
            person_ids = interactions["last_event"].get("person_ids", [])
            meeting_data["teamMemberIds"] = person_ids
            if client and person_ids:
                meeting_data["teamMemberNames"] = _resolve_person_names(
                    client, person_ids, person_name_cache
                )
        result["lastMeeting"] = meeting_data

    # Next meeting (next_event)
    if interaction_dates.next_event_date:
        meeting_data = {
            "date": _format_datetime(interaction_dates.next_event_date),
            "daysUntil": _days_until(interaction_dates.next_event_date, now),
        }
        if interactions and "next_event" in interactions:
            person_ids = interactions["next_event"].get("person_ids", [])
            meeting_data["teamMemberIds"] = person_ids
            if client and person_ids:
                meeting_data["teamMemberNames"] = _resolve_person_names(
                    client, person_ids, person_name_cache
                )
        result["nextMeeting"] = meeting_data

    # Last email
    if interaction_dates.last_email_date:
        email_data: dict[str, Any] = {
            "date": _format_datetime(interaction_dates.last_email_date),
            "daysSince": _days_since(interaction_dates.last_email_date, now),
        }
        if interactions and "last_email" in interactions:
            person_ids = interactions["last_email"].get("person_ids", [])
            email_data["teamMemberIds"] = person_ids
            if client and person_ids:
                email_data["teamMemberNames"] = _resolve_person_names(
                    client, person_ids, person_name_cache
                )
        result["lastEmail"] = email_data

    # Last interaction (any type)
    if interaction_dates.last_interaction_date:
        result["lastInteraction"] = {
            "date": _format_datetime(interaction_dates.last_interaction_date),
            "daysSince": _days_since(interaction_dates.last_interaction_date, now),
        }

    return result if result else None


def flatten_interactions_for_csv(interactions: dict[str, Any] | None) -> dict[str, str]:
    """Flatten nested interaction data for CSV columns.

    Returns dict with all INTERACTION_CSV_COLUMNS keys (empty strings if no data).

    Args:
        interactions: Transformed interaction data from transform_interaction_data()

    Returns:
        Dict with string values for each CSV column.
    """
    # Initialize all columns to empty string
    result: dict[str, str] = dict.fromkeys(INTERACTION_CSV_COLUMNS, "")

    if not interactions:
        return result

    # Last meeting
    if "lastMeeting" in interactions:
        last_meeting = interactions["lastMeeting"]
        result["lastMeetingDate"] = last_meeting.get("date", "")
        days_since = last_meeting.get("daysSince")
        result["lastMeetingDaysSince"] = str(days_since) if days_since is not None else ""
        team_names = last_meeting.get("teamMemberNames", [])
        result["lastMeetingTeamMembers"] = ", ".join(team_names) if team_names else ""

    # Next meeting
    if "nextMeeting" in interactions:
        next_meeting = interactions["nextMeeting"]
        result["nextMeetingDate"] = next_meeting.get("date", "")
        days_until = next_meeting.get("daysUntil")
        result["nextMeetingDaysUntil"] = str(days_until) if days_until is not None else ""
        team_names = next_meeting.get("teamMemberNames", [])
        result["nextMeetingTeamMembers"] = ", ".join(team_names) if team_names else ""

    # Last email
    if "lastEmail" in interactions:
        last_email = interactions["lastEmail"]
        result["lastEmailDate"] = last_email.get("date", "")
        days_since = last_email.get("daysSince")
        result["lastEmailDaysSince"] = str(days_since) if days_since is not None else ""

    # Last interaction
    if "lastInteraction" in interactions:
        last_interaction = interactions["lastInteraction"]
        result["lastInteractionDate"] = last_interaction.get("date", "")
        days_since = last_interaction.get("daysSince")
        result["lastInteractionDaysSince"] = str(days_since) if days_since is not None else ""

    return result


# =============================================================================
# Helper Functions
# =============================================================================


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime as ISO 8601 string."""
    if dt is None:
        return ""
    return dt.isoformat()


def _days_since(dt: datetime, now: datetime) -> int:
    """Calculate days since a datetime (positive if in past)."""
    diff = now - dt
    return max(0, diff.days)


def _days_until(dt: datetime, now: datetime) -> int:
    """Calculate days until a datetime (positive if in future)."""
    diff = dt - now
    return max(0, diff.days)


def _resolve_person_names(
    client: Affinity,
    person_ids: list[int],
    cache: dict[int, str] | None = None,
) -> list[str]:
    """Resolve person IDs to names, using cache when available.

    Args:
        client: Affinity client for API calls
        person_ids: List of person IDs to resolve
        cache: Optional dict cache (mutated in place). Thread-safe under CPython GIL.

    Returns:
        List of person names in same order as input IDs.
        Uses "Unknown" for any IDs that fail to resolve.
    """
    if cache is None:
        cache = {}

    names: list[str] = []
    for pid in person_ids:
        if pid in cache:
            names.append(cache[pid])
            continue

        try:
            # Fetch person name from API
            from affinity.types import PersonId

            person = client.persons.get(PersonId(pid))
            name = person.full_name or f"Person {pid}"
            cache[pid] = name
            names.append(name)
        except Exception:
            # Cache as Unknown to avoid repeated failures
            cache[pid] = f"Person {pid}"
            names.append(f"Person {pid}")

    return names


async def _resolve_person_names_async(
    client: AsyncAffinity,
    person_ids: list[int],
    cache: dict[int, str] | None = None,
    *,
    person_semaphore: asyncio.Semaphore | None = None,
) -> list[str]:
    """Resolve person IDs to names asynchronously, using cache when available.

    Person fetches run in parallel with bounded concurrency via a SHARED semaphore.

    Args:
        client: AsyncAffinity client for async API calls
        person_ids: List of person IDs to resolve
        cache: Optional dict cache (mutated in place). Thread-safe under CPython GIL.
        person_semaphore: Optional SHARED semaphore for bounded concurrent fetches.
            IMPORTANT: Pass the same semaphore across all calls to limit total
            concurrent person API calls. Creating a new semaphore per call defeats
            the bounded concurrency purpose.

    Returns:
        List of person names in same order as input IDs.
        Uses "Person {id}" for any IDs that fail to resolve.
    """
    if cache is None:
        cache = {}

    # NOTE: Benign race possible - two tasks may both see same ID as uncached
    # before either updates cache. Result: duplicate fetch, correct final state.
    uncached_ids = [pid for pid in person_ids if pid not in cache]

    if uncached_ids:
        # Use SHARED semaphore from caller, or create local fallback (for backwards compat)
        sem = person_semaphore or asyncio.Semaphore(10)

        async def fetch_person(pid: int) -> None:
            async with sem:
                try:
                    from affinity.types import PersonId

                    person = await client.persons.get(PersonId(pid))
                    name = person.full_name or f"Person {pid}"
                    cache[pid] = name
                except Exception:
                    # Cache as fallback to avoid repeated failures
                    cache[pid] = f"Person {pid}"

        # PERF: Parallelize person fetches with bounded concurrency
        await asyncio.gather(*[fetch_person(pid) for pid in uncached_ids])

    # Return names in original order
    return [cache.get(pid, f"Person {pid}") for pid in person_ids]


# PERF: section_iteration_boundary
async def resolve_interaction_names_async(
    client: AsyncAffinity,
    interaction_data: dict[str, Any] | None,
    cache: dict[int, str] | None = None,
    *,
    person_semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Resolve teamMemberNames in transformed interaction data asynchronously.

    Mutates the interaction_data dict in place, adding teamMemberNames
    to any section that has teamMemberIds.

    Sections (lastMeeting, nextMeeting, lastEmail) are resolved in parallel.
    Person fetches within each section use a SHARED semaphore for bounded concurrency.

    Args:
        client: AsyncAffinity client for async API calls
        interaction_data: Transformed interaction data from transform_interaction_data()
        cache: Optional dict cache for person names (mutated in place)
        person_semaphore: Optional SHARED semaphore for bounded person resolution.
            If not provided, a local semaphore is created (not recommended for
            multi-record expansion - pass shared semaphore from caller).
    """
    if interaction_data is None:
        return

    if cache is None:
        cache = {}

    async def resolve_section(section_key: str) -> None:
        """Resolve person names for a single section."""
        section = interaction_data.get(section_key)
        if section and "teamMemberIds" in section:
            person_ids = section["teamMemberIds"]
            if person_ids:
                section["teamMemberNames"] = await _resolve_person_names_async(
                    client, person_ids, cache, person_semaphore=person_semaphore
                )

    # PERF: Parallelize over sections (lastMeeting, nextMeeting, lastEmail)
    await asyncio.gather(
        *[resolve_section(key) for key in ("lastMeeting", "nextMeeting", "lastEmail")]
    )


# =============================================================================
# Unreplied Email Detection
# =============================================================================


def check_unreplied_email(
    client: Affinity,
    entity_type: str,
    entity_id: int,
    lookback_days: int = 30,
) -> dict[str, Any] | None:
    """Check for unreplied incoming emails for an entity.

    Fetches recent email interactions and checks if the most recent
    incoming email has a subsequent outgoing reply.

    Args:
        client: Affinity client for API calls
        entity_type: "company" or "person"
        entity_id: The entity ID
        lookback_days: Number of days to look back for emails (default 30)

    Returns:
        Dict with unreplied email info if found, None otherwise.
        Example: {
            "date": "2026-01-10T10:00:00Z",
            "daysSince": 5,
            "subject": "Following up on our conversation",
        }
    """
    from affinity.models.types import InteractionDirection, InteractionType
    from affinity.types import CompanyId, PersonId

    try:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=lookback_days)

        # Fetch email interactions for the entity
        if entity_type == "company":
            emails = list(
                client.interactions.iter(
                    company_id=CompanyId(entity_id),
                    type=InteractionType.EMAIL,
                    start_time=start_time,
                    end_time=now,
                )
            )
        elif entity_type == "person":
            emails = list(
                client.interactions.iter(
                    person_id=PersonId(entity_id),
                    type=InteractionType.EMAIL,
                    start_time=start_time,
                    end_time=now,
                )
            )
        else:
            logger.debug(f"Unsupported entity type for unreplied email check: {entity_type}")
            return None

        if not emails:
            return None

        # Sort by date descending (most recent first)
        emails.sort(key=lambda e: e.date, reverse=True)

        # Find the most recent incoming email
        last_incoming = None
        for email in emails:
            if email.direction == InteractionDirection.INCOMING:
                last_incoming = email
                break

        if not last_incoming:
            return None

        # Check if there's an outgoing email after the last incoming
        has_reply = any(
            e.direction == InteractionDirection.OUTGOING and e.date > last_incoming.date
            for e in emails
        )

        if has_reply:
            return None

        # Return unreplied email info
        return {
            "date": _format_datetime(last_incoming.date),
            "daysSince": _days_since(last_incoming.date, now),
            "subject": last_incoming.subject,
        }

    except Exception as e:
        logger.warning(f"Failed to check unreplied emails for {entity_type} {entity_id}: {e}")
        return None


async def async_check_unreplied_email(
    client: AsyncAffinity,
    entity_type: str | int,
    entity_id: int,
    lookback_days: int = 30,
) -> dict[str, Any] | None:
    """Async version: Check for unreplied incoming emails for an entity.

    Supports person, company, and opportunity entity types.
    Also handles V1 integer entityType formats (0=person, 1=company).

    Args:
        client: AsyncAffinity client for API calls
        entity_type: "company", "person", "opportunity" (or V1 integers 0, 1)
        entity_id: The entity ID
        lookback_days: Number of days to look back for emails (default 30)

    Returns:
        Dict with unreplied email info if found, None otherwise.
        Example: {
            "date": "2026-01-10T10:00:00Z",
            "daysSince": 5,
            "subject": "Following up on our conversation",
        }
    """
    from affinity.models.types import InteractionDirection, InteractionType
    from affinity.types import CompanyId, OpportunityId, PersonId

    try:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=lookback_days)

        # Build entity-specific filter kwargs
        # Handle V1 (integer) and V2 (string) entityType formats
        iter_kwargs: dict[str, Any] = {
            "type": InteractionType.EMAIL,
            "start_time": start_time,
            "end_time": now,
        }

        if entity_type in ("company", 1, "organization"):
            iter_kwargs["company_id"] = CompanyId(entity_id)
        elif entity_type in ("person", 0):
            iter_kwargs["person_id"] = PersonId(entity_id)
        elif entity_type == "opportunity":
            iter_kwargs["opportunity_id"] = OpportunityId(entity_id)
        else:
            logger.debug(f"Unsupported entity type for unreplied email check: {entity_type}")
            return None

        # Fetch email interactions for the entity
        emails = []
        async for email in client.interactions.iter(**iter_kwargs):
            emails.append(email)

        if not emails:
            return None

        # Sort by date descending (most recent first)
        emails.sort(key=lambda e: e.date, reverse=True)

        # Find the most recent incoming email
        last_incoming = None
        for email in emails:
            if email.direction == InteractionDirection.INCOMING:
                last_incoming = email
                break

        if not last_incoming:
            return None

        # Check if there's an outgoing email after the last incoming
        has_reply = any(
            e.direction == InteractionDirection.OUTGOING and e.date > last_incoming.date
            for e in emails
        )

        if has_reply:
            return None

        # Return unreplied email info
        return {
            "date": _format_datetime(last_incoming.date),
            "daysSince": _days_since(last_incoming.date, now),
            "subject": last_incoming.subject,
        }

    except Exception as e:
        logger.warning(f"Failed to check unreplied emails for {entity_type} {entity_id}: {e}")
        return None


def flatten_unreplied_email_for_csv(unreplied: dict[str, Any] | None) -> dict[str, str]:
    """Flatten unreplied email data for CSV columns.

    Returns dict with all UNREPLIED_EMAIL_CSV_COLUMNS keys (empty strings if no data).

    Args:
        unreplied: Unreplied email data from check_unreplied_email()

    Returns:
        Dict with string values for each CSV column.
    """
    result: dict[str, str] = dict.fromkeys(UNREPLIED_EMAIL_CSV_COLUMNS, "")

    if not unreplied:
        return result

    result["unrepliedEmailDate"] = unreplied.get("date", "")
    days_since = unreplied.get("daysSince")
    result["unrepliedEmailDaysSince"] = str(days_since) if days_since is not None else ""
    result["unrepliedEmailSubject"] = unreplied.get("subject") or ""

    return result
