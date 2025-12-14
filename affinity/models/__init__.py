"""
Affinity data models.

All Pydantic models and type definitions are available from this module.
"""

from __future__ import annotations

# Core entities
from .entities import (
    # List
    AffinityList,
    ListSummary,
    # Base
    AffinityModel,
    # Company
    Company,
    CompanyCreate,
    CompanyUpdate,
    DropdownOption,
    FieldCreate,
    # Field
    FieldMetadata,
    FieldValue,
    FieldValueCreate,
    ListCreate,
    # List Entry
    ListEntry,
    ListEntryCreate,
    ListEntryWithEntity,
    ListPermission,
    # Opportunity
    Opportunity,
    OpportunityCreate,
    # Person
    Person,
    PersonCreate,
    PersonUpdate,
    # Saved View
    SavedView,
)

# Pagination
from .pagination import (
    AsyncPageIterator,
    BatchOperationResponse,
    BatchOperationResult,
    PageIterator,
    PaginatedResponse,
    PaginationInfo,
)

# Secondary models
from .secondary import (
    # File
    EntityFile,
    Grant,
    # Interaction
    Interaction,
    InteractionCreate,
    InteractionUpdate,
    # Note
    Note,
    NoteCreate,
    NoteUpdate,
    RateLimitInfo,
    RateLimits,
    # Relationship
    RelationshipStrength,
    # Reminder
    Reminder,
    ReminderCreate,
    ReminderUpdate,
    Tenant,
    WebhookCreate,
    # Webhook
    WebhookSubscription,
    WebhookUpdate,
    # Auth
    WhoAmI,
)

# Type system
from .types import (
    # Base URLs
    V1_BASE_URL,
    V2_BASE_URL,
    AnyFieldId,
    CompanyId,
    DropdownOptionColor,
    EnrichedFieldId,
    EntityType,
    FieldId,
    FieldType,
    FieldValueId,
    FieldValueType,
    FileId,
    InteractionType,
    ListEntryId,
    ListId,
    # Enums
    ListType,
    NoteId,
    NoteType,
    OpportunityId,
    # ID types
    PersonId,
    PersonType,
    ReminderIdType,
    ReminderResetType,
    ReminderStatus,
    ReminderType,
    SavedViewId,
    UserId,
    WebhookEventType,
    WebhookId,
)

__all__ = [
    # URLs
    "V1_BASE_URL",
    "V2_BASE_URL",
    # ID types
    "PersonId",
    "CompanyId",
    "OpportunityId",
    "ListId",
    "ListEntryId",
    "FieldId",
    "FieldValueId",
    "EnrichedFieldId",
    "AnyFieldId",
    "NoteId",
    "UserId",
    "WebhookId",
    "FileId",
    "SavedViewId",
    "ReminderIdType",
    # Enums
    "ListType",
    "PersonType",
    "EntityType",
    "FieldValueType",
    "FieldType",
    "DropdownOptionColor",
    "InteractionType",
    "NoteType",
    "ReminderType",
    "ReminderResetType",
    "ReminderStatus",
    "WebhookEventType",
    # Base
    "AffinityModel",
    # Person
    "Person",
    "PersonCreate",
    "PersonUpdate",
    # Company
    "Company",
    "CompanyCreate",
    "CompanyUpdate",
    # Opportunity
    "Opportunity",
    "OpportunityCreate",
    # List
    "AffinityList",
    "ListSummary",
    "ListCreate",
    "ListPermission",
    # List Entry
    "ListEntry",
    "ListEntryCreate",
    "ListEntryWithEntity",
    # Field
    "FieldMetadata",
    "FieldCreate",
    "FieldValue",
    "FieldValueCreate",
    "DropdownOption",
    # Saved View
    "SavedView",
    # Note
    "Note",
    "NoteCreate",
    "NoteUpdate",
    # Reminder
    "Reminder",
    "ReminderCreate",
    "ReminderUpdate",
    # Webhook
    "WebhookSubscription",
    "WebhookCreate",
    "WebhookUpdate",
    # Interaction
    "Interaction",
    "InteractionCreate",
    "InteractionUpdate",
    # File
    "EntityFile",
    # Relationship
    "RelationshipStrength",
    # Auth
    "WhoAmI",
    "RateLimits",
    "RateLimitInfo",
    "Tenant",
    "Grant",
    # Pagination
    "PaginationInfo",
    "PaginatedResponse",
    "PageIterator",
    "AsyncPageIterator",
    "BatchOperationResponse",
    "BatchOperationResult",
]
