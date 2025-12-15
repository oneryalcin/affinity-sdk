"""
Strongly-typed IDs and core type definitions for the Affinity API.

This module provides type-safe ID wrappers to prevent mixing up different entity IDs.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum, IntEnum
from typing import Annotated, Any, SupportsInt, TypeAlias, cast

from pydantic import Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

# =============================================================================
# Typed IDs - These provide type safety to prevent mixing up different entity IDs
# =============================================================================


class IntId(int):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        _ = source_type
        return core_schema.no_info_after_validator_function(cls, handler(int))


class StrId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        _ = source_type
        return core_schema.no_info_after_validator_function(cls, handler(str))


class PersonId(IntId):
    pass


class CompanyId(IntId):
    """Called Organization in V1."""


class OpportunityId(IntId):
    pass


class ListId(IntId):
    pass


class ListEntryId(IntId):
    pass


_FIELD_ID_RE = re.compile(r"^field-(\d+)$")


class FieldId(StrId):
    """V2-style field id (e.g. 'field-123')."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        _ = source_type
        _ = handler

        def validate(value: Any) -> FieldId:
            if isinstance(value, cls):
                return value
            if isinstance(value, int):
                return cls(f"field-{value}")
            if isinstance(value, str):
                candidate = value.strip()
                if candidate.isdigit():
                    return cls(f"field-{candidate}")
                if _FIELD_ID_RE.match(candidate):
                    return cls(candidate)
            raise ValueError("FieldId must be an int, digits, or 'field-<digits>'")

        return core_schema.no_info_plain_validator_function(validate)


class FieldValueId(IntId):
    pass


class NoteId(IntId):
    pass


class ReminderIdType(IntId):
    pass


class WebhookId(IntId):
    pass


class InteractionId(IntId):
    pass


class FileId(IntId):
    pass


class SavedViewId(IntId):
    pass


class DropdownOptionId(IntId):
    pass


class UserId(IntId):
    pass


class TenantId(IntId):
    pass


class TaskId(StrId):
    """UUIDs for async tasks."""


class EnrichedFieldId(StrId):
    """Enriched field IDs are strings in V2 (e.g., 'affinity-data-description')."""


# Combined Field ID type - can be either numeric or string
AnyFieldId: TypeAlias = FieldId | EnrichedFieldId


def field_id_to_v1_numeric(field_id: AnyFieldId) -> int:
    """
    Convert v2 FieldId into v1 numeric field_id.

    Accepts:
    - FieldId('field-123') -> 123
    Rejects:
    - EnrichedFieldId(...) (cannot be represented as v1 numeric id)
    """
    if isinstance(field_id, EnrichedFieldId):
        raise ValueError("Enriched field IDs cannot be converted to v1 numeric field_id")

    match = _FIELD_ID_RE.match(str(field_id))
    if match is None:
        raise ValueError("FieldId must match 'field-<digits>' for v1 conversion")
    return int(match.group(1))


# =============================================================================
# Enums - Replace all magic numbers with type-safe enums
# =============================================================================


class OpenIntEnum(IntEnum):
    @classmethod
    def _missing_(cls, value: object) -> OpenIntEnum:
        try:
            int_value = int(cast(SupportsInt | str | bytes | bytearray, value))
        except (TypeError, ValueError) as e:
            raise ValueError(value) from e

        obj = int.__new__(cls, int_value)
        obj._value_ = int_value
        obj._name_ = f"UNKNOWN_{int_value}"
        cls._value2member_map_[int_value] = obj
        return obj


class OpenStrEnum(str, Enum):
    @classmethod
    def _missing_(cls, value: object) -> OpenStrEnum:
        text = str(value)
        obj = str.__new__(cls, text)
        obj._value_ = text
        obj._name_ = f"UNKNOWN_{text}"
        cls._value2member_map_[text] = obj
        return obj


class ListType(OpenIntEnum):
    """Type of entities a list can contain."""

    PERSON = 0
    ORGANIZATION = 1  # Company in V2 terminology
    OPPORTUNITY = 8


class EntityType(OpenIntEnum):
    """Entity types in Affinity."""

    PERSON = 0
    ORGANIZATION = 1
    OPPORTUNITY = 8


class PersonType(OpenStrEnum):
    """Types of persons in Affinity."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    COLLABORATOR = "collaborator"


class FieldValueType(OpenIntEnum):
    """
    Field value types - determines what kind of data a field can hold.

    From V1 API documentation:
    """

    PERSON = 0
    ORGANIZATION = 1  # Company
    TEXT = 2
    NUMBER = 3
    DATE = 4
    LOCATION = 5
    # Note: 6 is not used
    DROPDOWN = 7  # Ranked dropdown
    # Additional V2 types
    FILTERABLE_TEXT = 10


class FieldType(OpenStrEnum):
    """
    Field types based on their source/scope.
    V2 API uses these string identifiers.
    """

    ENRICHED = "enriched"
    LIST = "list"
    LIST_SPECIFIC = "list-specific"  # Alias used in some API responses
    GLOBAL = "global"
    RELATIONSHIP_INTELLIGENCE = "relationship-intelligence"


class InteractionType(OpenIntEnum):
    """Types of interactions."""

    MEETING = 0  # Also called Event
    CALL = 1
    CHAT_MESSAGE = 2
    EMAIL = 3


class InteractionDirection(OpenIntEnum):
    """Direction of communication for interactions."""

    OUTGOING = 0
    INCOMING = 1


class InteractionLoggingType(OpenIntEnum):
    """How the interaction was logged."""

    AUTOMATIC = 0
    MANUAL = 1


class ReminderType(OpenIntEnum):
    """Types of reminders."""

    ONE_TIME = 0
    RECURRING = 1


class ReminderResetType(OpenIntEnum):
    """How recurring reminders get reset."""

    INTERACTION = 0  # Email or meeting
    EMAIL = 1
    MEETING = 2


class ReminderStatus(OpenIntEnum):
    """Current status of a reminder."""

    COMPLETED = 0
    ACTIVE = 1
    OVERDUE = 2


class NoteType(OpenIntEnum):
    """Types of notes."""

    PLAIN_TEXT = 0
    EMAIL_DERIVED = 1  # Deprecated creation method
    HTML = 2
    AI_NOTETAKER = 3


class ListRole(OpenIntEnum):
    """Roles for list-level permissions."""

    ADMIN = 0
    BASIC = 1
    STANDARD = 2


class FieldValueChangeAction(OpenIntEnum):
    """Types of changes that can occur to field values."""

    CREATE = 0
    DELETE = 1
    UPDATE = 2


class WebhookEvent(OpenStrEnum):
    """Supported webhook events."""

    LIST_CREATED = "list.created"
    LIST_UPDATED = "list.updated"
    LIST_DELETED = "list.deleted"
    LIST_ENTRY_CREATED = "list_entry.created"
    LIST_ENTRY_DELETED = "list_entry.deleted"
    NOTE_CREATED = "note.created"
    NOTE_UPDATED = "note.updated"
    NOTE_DELETED = "note.deleted"
    FIELD_CREATED = "field.created"
    FIELD_UPDATED = "field.updated"
    FIELD_DELETED = "field.deleted"
    FIELD_VALUE_CREATED = "field_value.created"
    FIELD_VALUE_UPDATED = "field_value.updated"
    FIELD_VALUE_DELETED = "field_value.deleted"
    PERSON_CREATED = "person.created"
    PERSON_UPDATED = "person.updated"
    PERSON_DELETED = "person.deleted"
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    ORGANIZATION_DELETED = "organization.deleted"
    ORGANIZATION_MERGED = "organization.merged"
    OPPORTUNITY_CREATED = "opportunity.created"
    OPPORTUNITY_UPDATED = "opportunity.updated"
    OPPORTUNITY_DELETED = "opportunity.deleted"
    FILE_CREATED = "file.created"
    FILE_DELETED = "file.deleted"
    REMINDER_CREATED = "reminder.created"
    REMINDER_UPDATED = "reminder.updated"
    REMINDER_DELETED = "reminder.deleted"


class DropdownOptionColor(IntEnum):
    """
    Colors for dropdown options.

    Affinity uses integer color codes for dropdown field options.
    """

    DEFAULT = 0
    BLUE = 1
    GREEN = 2
    YELLOW = 3
    ORANGE = 4
    RED = 5
    PURPLE = 6
    GRAY = 7


class MergeStatus(str, Enum):
    """Status of async merge operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


# =============================================================================
# API Version tracking
# =============================================================================


class APIVersion(str, Enum):
    """API versions with their base URLs."""

    V1 = "v1"
    V2 = "v2"


# Base URLs
V1_BASE_URL = "https://api.affinity.co"
V2_BASE_URL = "https://api.affinity.co/v2"


# =============================================================================
# Common type aliases with validation
# =============================================================================

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
EmailStr = Annotated[str, Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")]

# Datetime with ISO8601 format
ISODatetime = datetime


# =============================================================================
# Filter operators for V2 API query language
# =============================================================================


class FilterOperator(str, Enum):
    """Operators for V2 filtering."""

    EQUALS = "="
    NOT_EQUALS = "!="
    STARTS_WITH = "=^"
    ENDS_WITH = "=$"
    CONTAINS = "=~"
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    IS_NULL = "!= *"
    IS_NOT_NULL = "= *"
    IS_EMPTY = '= ""'
