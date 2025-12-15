"""
Affinity data models.

All Pydantic models are available from this module.

Tip:
    ID types and enums live in `affinity.types`.
"""

from __future__ import annotations

# Core entities
from .entities import (
    # List
    AffinityList,
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
    ListSummary,
    # Opportunity
    Opportunity,
    OpportunityCreate,
    OpportunityUpdate,
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

__all__ = [
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
    "OpportunityUpdate",
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
