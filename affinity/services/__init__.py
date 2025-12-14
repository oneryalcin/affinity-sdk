"""
API service implementations.
"""

from .companies import CompanyService
from .lists import ListEntryService, ListService
from .opportunities import OpportunityService
from .persons import PersonService
from .v1_only import (
    AuthService,
    EntityFileService,
    FieldService,
    FieldValueService,
    InteractionService,
    NoteService,
    RelationshipStrengthService,
    ReminderService,
    WebhookService,
)

__all__ = [
    # V2+V1 hybrid services
    "CompanyService",
    "PersonService",
    "ListService",
    "ListEntryService",
    "OpportunityService",
    # V1-only services
    "NoteService",
    "ReminderService",
    "WebhookService",
    "InteractionService",
    "FieldService",
    "FieldValueService",
    "RelationshipStrengthService",
    "EntityFileService",
    "AuthService",
]
