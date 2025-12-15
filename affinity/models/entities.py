"""
Core entity models for the Affinity API.

These models represent the main entities in Affinity: Persons, Companies,
Opportunities, Lists, and List Entries. Uses V2 terminology throughout.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .types import (
    AnyFieldId,
    CompanyId,
    EntityType,
    FieldId,
    FieldValueType,
    ISODatetime,
    ListEntryId,
    ListId,
    ListRole,
    ListType,
    OpportunityId,
    PersonId,
    PersonType,
    SavedViewId,
    UserId,
)

# =============================================================================
# Base configuration for all models
# =============================================================================


class AffinityModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        extra="ignore",  # Ignore unknown fields from API
        populate_by_name=True,  # Allow both alias and field name
        use_enum_values=True,  # Serialize enums as values
        validate_assignment=True,  # Validate on attribute assignment
    )


class FieldValues(AffinityModel):
    """
    Field values container that preserves the "requested vs not requested"
    semantics.

    - `requested=False` means the caller did not request field data and/or the
      API omitted field data.
    - `requested=True` means field data was requested and returned (possibly
      empty/null-normalized).
    """

    requested: bool = False
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_api(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if value is None:
            return {"requested": True, "data": {}}
        if isinstance(value, dict):
            return {"requested": True, "data": value}
        return {"requested": True, "data": {}}


def _normalize_null_lists(value: Any, keys: Sequence[str]) -> Any:
    if not isinstance(value, Mapping):
        return value

    data: dict[str, Any] = dict(value)
    for key in keys:
        if key in data and data[key] is None:
            data[key] = []
    return data


# =============================================================================
# Location Value
# =============================================================================


class Location(AffinityModel):
    """Geographic location value."""

    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    continent: str | None = None


# =============================================================================
# Dropdown Option
# =============================================================================


class DropdownOption(AffinityModel):
    """A selectable option in a dropdown field."""

    id: int
    text: str
    rank: int | None = None
    color: int | None = None


# =============================================================================
# Person Models
# =============================================================================


class PersonSummary(AffinityModel):
    """Minimal person data returned in nested contexts."""

    id: PersonId
    first_name: str | None = Field(None, alias="firstName")
    last_name: str | None = Field(None, alias="lastName")
    primary_email: str | None = Field(None, alias="primaryEmailAddress")
    type: PersonType


class Person(AffinityModel):
    """
    Full person representation.

    Note: Companies are called Organizations in V1 API.
    """

    id: PersonId
    first_name: str | None = Field(None, alias="firstName")
    last_name: str | None = Field(None, alias="lastName")
    primary_email: str | None = Field(None, alias="primaryEmailAddress")
    # V2 uses emailAddresses, V1 uses emails - accept both via alias
    emails: list[str] = Field(default_factory=list, alias="emailAddresses")
    type: PersonType = PersonType.EXTERNAL

    # Associations (V1 uses organization_ids)
    organization_ids: list[CompanyId] = Field(default_factory=list, alias="organizationIds")
    opportunity_ids: list[OpportunityId] = Field(default_factory=list, alias="opportunityIds")

    # Field values (requested-vs-not-requested preserved)
    fields: FieldValues = Field(default_factory=FieldValues, alias="fields")

    @model_validator(mode="before")
    @classmethod
    def _normalize_null_lists_before(cls, value: Any) -> Any:
        return _normalize_null_lists(
            value,
            (
                "emails",
                "emailAddresses",
                "organizationIds",
                "organization_ids",
                "opportunityIds",
                "opportunity_ids",
            ),
        )

    @model_validator(mode="after")
    def _mark_fields_not_requested_when_omitted(self) -> Person:
        if "fields" not in self.__pydantic_fields_set__:
            self.fields.requested = False
        return self

    # Interaction dates (V1 format, returned when with_interaction_dates=True)
    interaction_dates: InteractionDates | None = Field(None, alias="interactionDates")

    @property
    def full_name(self) -> str:
        """Get the person's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or ""


class PersonCreate(AffinityModel):
    """Data for creating a new person (V1 API)."""

    first_name: str
    last_name: str
    emails: list[str] = Field(default_factory=list)
    organization_ids: list[CompanyId] = Field(default_factory=list)


class PersonUpdate(AffinityModel):
    """Data for updating a person (V1 API)."""

    first_name: str | None = None
    last_name: str | None = None
    emails: list[str] | None = None
    organization_ids: list[CompanyId] | None = None


# =============================================================================
# Company (Organization) Models
# =============================================================================


class CompanySummary(AffinityModel):
    """Minimal company data returned in nested contexts."""

    id: CompanyId
    name: str
    domain: str | None = None


class Company(AffinityModel):
    """
    Full company representation.

    Note: Called Organization in V1 API.
    """

    id: CompanyId
    name: str
    domain: str | None = None
    domains: list[str] = Field(default_factory=list)
    is_global: bool = Field(False, alias="global")

    # Associations
    person_ids: list[PersonId] = Field(default_factory=list, alias="personIds")
    opportunity_ids: list[OpportunityId] = Field(default_factory=list, alias="opportunityIds")

    # Field values (requested-vs-not-requested preserved)
    fields: FieldValues = Field(default_factory=FieldValues, alias="fields")

    @model_validator(mode="before")
    @classmethod
    def _normalize_null_lists_before(cls, value: Any) -> Any:
        return _normalize_null_lists(
            value,
            (
                "domains",
                "personIds",
                "person_ids",
                "opportunityIds",
                "opportunity_ids",
            ),
        )

    @model_validator(mode="after")
    def _mark_fields_not_requested_when_omitted(self) -> Company:
        if "fields" not in self.__pydantic_fields_set__:
            self.fields.requested = False
        return self

    # List entries (returned for single company fetch)
    list_entries: list[ListEntry] | None = Field(None, alias="listEntries")

    # Interaction dates
    interaction_dates: InteractionDates | None = Field(None, alias="interactionDates")


class CompanyCreate(AffinityModel):
    """Data for creating a new company (V1 API)."""

    name: str
    domain: str | None = None
    person_ids: list[PersonId] = Field(default_factory=list)


class CompanyUpdate(AffinityModel):
    """Data for updating a company (V1 API)."""

    name: str | None = None
    domain: str | None = None
    person_ids: list[PersonId] | None = None


# =============================================================================
# Opportunity Models
# =============================================================================


class Opportunity(AffinityModel):
    """Deal/opportunity in a pipeline."""

    id: OpportunityId
    name: str
    list_id: ListId = Field(alias="listId")

    # Associations
    person_ids: list[PersonId] = Field(default_factory=list, alias="personIds")
    organization_ids: list[CompanyId] = Field(default_factory=list, alias="organizationIds")

    # Field values (requested-vs-not-requested preserved)
    fields: FieldValues = Field(default_factory=FieldValues, alias="fields")

    @model_validator(mode="after")
    def _mark_fields_not_requested_when_omitted(self) -> Opportunity:
        if "fields" not in self.__pydantic_fields_set__:
            self.fields.requested = False
        return self

    # List entries
    list_entries: list[ListEntry] | None = Field(None, alias="listEntries")


class OpportunityCreate(AffinityModel):
    """Data for creating a new opportunity (V1 API)."""

    name: str
    list_id: ListId
    person_ids: list[PersonId] = Field(default_factory=list)
    organization_ids: list[CompanyId] = Field(default_factory=list)


class OpportunityUpdate(AffinityModel):
    """Data for updating an opportunity (V1 API)."""

    name: str | None = None
    person_ids: list[PersonId] | None = None
    organization_ids: list[CompanyId] | None = None


# =============================================================================
# List Models
# =============================================================================


class ListPermission(AffinityModel):
    """Additional permission on a list."""

    internal_person_id: UserId = Field(alias="internalPersonId")
    role_id: ListRole = Field(alias="roleId")


class AffinityList(AffinityModel):
    """
    A list (spreadsheet) in Affinity.

    Named AffinityList to avoid collision with Python's list type.
    """

    id: ListId
    name: str
    type: ListType
    is_public: bool = Field(alias="public")
    owner_id: UserId = Field(alias="ownerId")
    creator_id: UserId | None = Field(None, alias="creatorId")
    list_size: int = Field(0, alias="listSize")

    # Fields on this list (returned for single list fetch)
    fields: list[FieldMetadata] | None = None

    # Permissions
    additional_permissions: list[ListPermission] = Field(
        default_factory=list, alias="additionalPermissions"
    )


class ListSummary(AffinityModel):
    """Minimal list reference used by relationship endpoints."""

    id: ListId
    name: str | None = None
    type: ListType | None = None
    is_public: bool | None = Field(None, alias="public")
    owner_id: UserId | None = Field(None, alias="ownerId")
    list_size: int | None = Field(None, alias="listSize")


class ListCreate(AffinityModel):
    """Data for creating a new list (V1 API)."""

    name: str
    type: ListType
    is_public: bool
    owner_id: UserId | None = None
    additional_permissions: list[ListPermission] = Field(default_factory=list)


# =============================================================================
# List Entry Models
# =============================================================================


class ListEntry(AffinityModel):
    """
    A row in a list, linking an entity to a list.

    Contains the entity data and list-specific field values.
    """

    id: ListEntryId
    list_id: ListId = Field(alias="listId")
    creator_id: UserId | None = Field(None, alias="creatorId")
    entity_id: int | None = Field(None, alias="entityId")
    entity_type: EntityType | None = Field(None, alias="entityType")
    created_at: ISODatetime = Field(alias="createdAt")

    # The entity this entry represents (can be Person, Company, or Opportunity)
    entity: PersonSummary | CompanySummary | dict[str, Any] | None = None

    # Field values on this list entry (requested-vs-not-requested preserved)
    fields: FieldValues = Field(default_factory=FieldValues, alias="fields")

    @model_validator(mode="after")
    def _mark_fields_not_requested_when_omitted(self) -> ListEntry:
        if "fields" not in self.__pydantic_fields_set__:
            self.fields.requested = False
        return self


class ListEntryWithEntity(AffinityModel):
    """List entry with full entity data included (V2 response format)."""

    id: ListEntryId
    list_id: ListId = Field(alias="listId")
    creator: PersonSummary | None = None
    created_at: ISODatetime = Field(alias="createdAt")

    # Entity type and data
    type: str  # "person", "company", or "opportunity"
    entity: Person | Company | Opportunity | None = None

    # Field values (requested-vs-not-requested preserved)
    fields: FieldValues = Field(default_factory=FieldValues, alias="fields")

    @model_validator(mode="after")
    def _mark_fields_not_requested_when_omitted(self) -> ListEntryWithEntity:
        if "fields" not in self.__pydantic_fields_set__:
            self.fields.requested = False
        return self


class ListEntryCreate(AffinityModel):
    """Data for adding an entity to a list (V1 API)."""

    entity_id: int
    creator_id: UserId | None = None


# =============================================================================
# Saved View Models
# =============================================================================


class SavedView(AffinityModel):
    """A saved view configuration for a list."""

    id: SavedViewId
    name: str
    type: str | None = None  # V2 field: view type
    list_id: ListId = Field(alias="listId")
    is_default: bool = Field(False, alias="isDefault")
    created_at: ISODatetime | None = Field(None, alias="createdAt")

    # Field IDs included in this view
    field_ids: list[str] = Field(default_factory=list, alias="fieldIds")


# =============================================================================
# Field Metadata Models
# =============================================================================


class FieldMetadata(AffinityModel):
    """
    Metadata about a field (column) in Affinity.

    Includes both V1 numeric IDs and V2 string IDs for enriched fields.
    """

    id: AnyFieldId  # Can be int (field-123) or string (affinity-data-description)
    name: str
    value_type: FieldValueType = Field(alias="valueType")
    allows_multiple: bool = Field(False, alias="allowsMultiple")

    # V2 field type classification
    type: str | None = None  # "enriched", "list-specific", "global", etc.

    # V1 specific fields
    list_id: ListId | None = Field(None, alias="listId")
    track_changes: bool = Field(False, alias="trackChanges")
    enrichment_source: str | None = Field(None, alias="enrichmentSource")
    is_required: bool = Field(False, alias="isRequired")

    # Dropdown options for dropdown fields
    dropdown_options: list[DropdownOption] = Field(default_factory=list, alias="dropdownOptions")


class FieldCreate(AffinityModel):
    """Data for creating a new field (V1 API)."""

    name: str
    entity_type: EntityType
    value_type: FieldValueType
    list_id: ListId | None = None
    allows_multiple: bool = False
    is_list_specific: bool = False
    is_required: bool = False


# =============================================================================
# Field Value Models
# =============================================================================


class FieldValue(AffinityModel):
    """
    A single field value (cell data).

    The value can be various types depending on the field's value_type.
    """

    id: int
    field_id: AnyFieldId = Field(alias="fieldId")
    entity_id: int = Field(alias="entityId")
    list_entry_id: ListEntryId | None = Field(None, alias="listEntryId")

    # The actual value - type depends on field type
    value: Any

    # Timestamps
    created_at: ISODatetime | None = Field(None, alias="createdAt")
    updated_at: ISODatetime | None = Field(None, alias="updatedAt")


class FieldValueCreate(AffinityModel):
    """Data for creating a field value (V1 API)."""

    field_id: FieldId
    entity_id: int
    value: Any
    list_entry_id: ListEntryId | None = None


class FieldValueUpdate(AffinityModel):
    """Data for updating a field value (V1 or V2 API)."""

    value: Any


# =============================================================================
# Field Value Change (History) Models
# =============================================================================


class FieldValueChange(AffinityModel):
    """Historical change to a field value."""

    id: int
    field_id: FieldId = Field(alias="fieldId")
    entity_id: int = Field(alias="entityId")
    list_entry_id: ListEntryId | None = Field(None, alias="listEntryId")
    action_type: int = Field(alias="actionType")  # 0=Create, 1=Delete, 2=Update
    value: Any
    changed_at: ISODatetime = Field(alias="changedAt")
    changer: PersonSummary | None = None


# =============================================================================
# Interaction Models
# =============================================================================


class InteractionDates(AffinityModel):
    """Dates of interactions with an entity."""

    first_email_date: ISODatetime | None = Field(None, alias="firstEmailDate")
    last_email_date: ISODatetime | None = Field(None, alias="lastEmailDate")
    first_event_date: ISODatetime | None = Field(None, alias="firstEventDate")
    last_event_date: ISODatetime | None = Field(None, alias="lastEventDate")
    next_event_date: ISODatetime | None = Field(None, alias="nextEventDate")
    last_chat_message_date: ISODatetime | None = Field(None, alias="lastChatMessageDate")
    last_interaction_date: ISODatetime | None = Field(None, alias="lastInteractionDate")


# Forward reference resolution
ListEntry.model_rebuild()
Company.model_rebuild()
