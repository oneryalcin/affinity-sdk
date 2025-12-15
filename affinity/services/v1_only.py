"""
V1-only services: Notes, Reminders, Webhooks, Interactions, Fields, and more.

These services wrap V1 API endpoints that don't have V2 equivalents.
"""

from __future__ import annotations

import builtins
import mimetypes
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..models.entities import FieldCreate, FieldMetadata, FieldValue, FieldValueCreate
from ..models.pagination import V1PaginatedResponse
from ..models.secondary import (
    EntityFile,
    Interaction,
    InteractionCreate,
    InteractionUpdate,
    Note,
    NoteCreate,
    NoteUpdate,
    RateLimits,
    RelationshipStrength,
    Reminder,
    ReminderCreate,
    ReminderUpdate,
    WebhookCreate,
    WebhookSubscription,
    WebhookUpdate,
    WhoAmI,
)
from ..models.types import (
    CompanyId,
    EntityType,
    FieldId,
    FieldValueId,
    FileId,
    InteractionType,
    ListId,
    NoteId,
    OpportunityId,
    PersonId,
    ReminderIdType,
    ReminderResetType,
    ReminderStatus,
    ReminderType,
    UserId,
    WebhookId,
    field_id_to_v1_numeric,
)
from ..progress import ProgressCallback

if TYPE_CHECKING:
    from ..clients.http import HTTPClient


# =============================================================================
# Notes Service (V1 API)
# =============================================================================


class NoteService:
    """
    Service for managing notes.

    V2 provides read-only access; use V1 for create/update/delete.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def list(
        self,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
        creator_id: UserId | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> V1PaginatedResponse[Note]:
        """
        Get notes filtered by entity or creator.

        Returns V1 paginated response with 'notes' and 'next_page_token'.
        """
        params: dict[str, Any] = {}
        if person_id:
            params["person_id"] = int(person_id)
        if organization_id:
            params["organization_id"] = int(organization_id)
        if opportunity_id:
            params["opportunity_id"] = int(opportunity_id)
        if creator_id:
            params["creator_id"] = int(creator_id)
        if page_size:
            params["page_size"] = page_size
        if page_token:
            params["page_token"] = page_token

        data = self._client.get("/notes", params=params or None, v1=True)
        items = data.get("notes", data.get("data", []))
        if not isinstance(items, list):
            items = []
        return V1PaginatedResponse[Note](
            data=[Note.model_validate(n) for n in items],
            next_page_token=data.get("next_page_token") or data.get("nextPageToken"),
        )

    def get(self, note_id: NoteId) -> Note:
        """Get a single note by ID."""
        data = self._client.get(f"/notes/{note_id}", v1=True)
        return Note.model_validate(data)

    def create(self, data: NoteCreate) -> Note:
        """
        Create a new note.

        Must be associated with at least one person, organization,
        opportunity, or parent note (for replies).
        """
        payload: dict[str, Any] = {
            "content": data.content,
            "type": int(data.type),
        }
        if data.person_ids:
            payload["person_ids"] = [int(p) for p in data.person_ids]
        if data.organization_ids:
            payload["organization_ids"] = [int(o) for o in data.organization_ids]
        if data.opportunity_ids:
            payload["opportunity_ids"] = [int(o) for o in data.opportunity_ids]
        if data.parent_id:
            payload["parent_id"] = int(data.parent_id)
        if data.creator_id:
            payload["creator_id"] = int(data.creator_id)
        if data.created_at:
            payload["created_at"] = data.created_at.isoformat()

        result = self._client.post("/notes", json=payload, v1=True)
        return Note.model_validate(result)

    def update(self, note_id: NoteId, data: NoteUpdate) -> Note:
        """Update a note's content."""
        result = self._client.put(
            f"/notes/{note_id}",
            json={"content": data.content},
            v1=True,
        )
        return Note.model_validate(result)

    def delete(self, note_id: NoteId) -> bool:
        """Delete a note."""
        result = self._client.delete(f"/notes/{note_id}", v1=True)
        return bool(result.get("success", False))


# =============================================================================
# Reminder Service (V1 API)
# =============================================================================


class ReminderService:
    """
    Service for managing reminders.

    Reminders are V1-only in this SDK (create/update/delete via V1).
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def list(
        self,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
        creator_id: UserId | None = None,
        owner_id: UserId | None = None,
        completer_id: UserId | None = None,
        type: ReminderType | None = None,
        reset_type: ReminderResetType | None = None,
        status: ReminderStatus | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> V1PaginatedResponse[Reminder]:
        """
        Get reminders with optional filtering.

        Returns V1 paginated response with `data` and `next_page_token`.
        """
        params: dict[str, Any] = {}
        if person_id:
            params["person_id"] = int(person_id)
        if organization_id:
            params["organization_id"] = int(organization_id)
        if opportunity_id:
            params["opportunity_id"] = int(opportunity_id)
        if creator_id:
            params["creator_id"] = int(creator_id)
        if owner_id:
            params["owner_id"] = int(owner_id)
        if completer_id:
            params["completer_id"] = int(completer_id)
        if type is not None:
            params["type"] = int(type)
        if reset_type is not None:
            params["reset_type"] = int(reset_type)
        if status is not None:
            params["status"] = int(status)
        if due_before:
            params["due_before"] = due_before.isoformat()
        if due_after:
            params["due_after"] = due_after.isoformat()
        if page_size:
            params["page_size"] = page_size
        if page_token:
            params["page_token"] = page_token

        data = self._client.get("/reminders", params=params or None, v1=True)
        items = data.get("reminders", data.get("data", []))
        if not isinstance(items, list):
            items = []
        return V1PaginatedResponse[Reminder](
            data=[Reminder.model_validate(r) for r in items],
            next_page_token=data.get("next_page_token") or data.get("nextPageToken"),
        )

    def get(self, reminder_id: ReminderIdType) -> Reminder:
        """Get a single reminder."""
        data = self._client.get(f"/reminders/{reminder_id}", v1=True)
        return Reminder.model_validate(data)

    def create(self, data: ReminderCreate) -> Reminder:
        """Create a new reminder."""
        payload: dict[str, Any] = {
            "owner_id": int(data.owner_id),
            "type": int(data.type),
        }
        if data.content:
            payload["content"] = data.content
        if data.due_date:
            payload["due_date"] = data.due_date.isoformat()
        if data.reset_type is not None:
            payload["reset_type"] = int(data.reset_type)
        if data.reminder_days is not None:
            payload["reminder_days"] = data.reminder_days
        if data.person_id:
            payload["person_id"] = int(data.person_id)
        if data.organization_id:
            payload["organization_id"] = int(data.organization_id)
        if data.opportunity_id:
            payload["opportunity_id"] = int(data.opportunity_id)

        result = self._client.post("/reminders", json=payload, v1=True)
        return Reminder.model_validate(result)

    def update(self, reminder_id: ReminderIdType, data: ReminderUpdate) -> Reminder:
        """Update a reminder."""
        payload: dict[str, Any] = {}
        if data.owner_id is not None:
            payload["owner_id"] = int(data.owner_id)
        if data.type is not None:
            payload["type"] = int(data.type)
        if data.content is not None:
            payload["content"] = data.content
        if data.due_date is not None:
            payload["due_date"] = data.due_date.isoformat()
        if data.reset_type is not None:
            payload["reset_type"] = int(data.reset_type)
        if data.reminder_days is not None:
            payload["reminder_days"] = data.reminder_days
        if data.is_completed is not None:
            payload["is_completed"] = data.is_completed

        result = self._client.put(f"/reminders/{reminder_id}", json=payload, v1=True)
        return Reminder.model_validate(result)

    def delete(self, reminder_id: ReminderIdType) -> bool:
        """Delete a reminder."""
        result = self._client.delete(f"/reminders/{reminder_id}", v1=True)
        return bool(result.get("success", False))


# =============================================================================
# Webhook Service (V1 API)
# =============================================================================


class WebhookService:
    """
    Service for managing webhook subscriptions.

    Note: Limited to 3 subscriptions per Affinity instance.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def list(self) -> builtins.list[WebhookSubscription]:
        """Get all webhook subscriptions."""
        data = self._client.get("/webhook", v1=True)
        return [WebhookSubscription.model_validate(w) for w in data.get("data", [])]

    def get(self, webhook_id: WebhookId) -> WebhookSubscription:
        """Get a single webhook subscription."""
        data = self._client.get(f"/webhook/{webhook_id}", v1=True)
        return WebhookSubscription.model_validate(data)

    def create(self, data: WebhookCreate) -> WebhookSubscription:
        """
        Create a webhook subscription.

        The webhook URL will receive a validation request.
        """
        payload: dict[str, Any] = {
            "webhook_url": data.webhook_url,
        }
        if data.subscriptions:
            payload["subscriptions"] = [str(s) for s in data.subscriptions]

        result = self._client.post("/webhook/subscribe", json=payload, v1=True)
        return WebhookSubscription.model_validate(result)

    def update(self, webhook_id: WebhookId, data: WebhookUpdate) -> WebhookSubscription:
        """Update a webhook subscription."""
        payload: dict[str, Any] = {}
        if data.webhook_url is not None:
            payload["webhook_url"] = data.webhook_url
        if data.subscriptions is not None:
            payload["subscriptions"] = [str(s) for s in data.subscriptions]
        if data.disabled is not None:
            payload["disabled"] = data.disabled

        result = self._client.put(f"/webhook/{webhook_id}", json=payload, v1=True)
        return WebhookSubscription.model_validate(result)

    def delete(self, webhook_id: WebhookId) -> bool:
        """Delete a webhook subscription."""
        result = self._client.delete(f"/webhook/{webhook_id}", v1=True)
        return bool(result.get("success", False))


# =============================================================================
# Interaction Service (V1 API)
# =============================================================================


class InteractionService:
    """
    Service for managing interactions (meetings, calls, emails, chats).

    V2 provides read-only metadata; V1 supports full CRUD.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def list(
        self,
        *,
        type: InteractionType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        person_id: PersonId | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> V1PaginatedResponse[Interaction]:
        """
        Get interactions with optional filtering.

        Returns V1 paginated response with `data` and `next_page_token`.
        """
        params: dict[str, Any] = {}
        if type is not None:
            params["type"] = int(type)
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if person_id:
            params["person_id"] = int(person_id)
        if page_size:
            params["page_size"] = page_size
        if page_token:
            params["page_token"] = page_token

        data = self._client.get("/interactions", params=params or None, v1=True)
        items: Any = None
        if type is not None:
            if int(type) in (int(InteractionType.MEETING), int(InteractionType.CALL)):
                items = data.get("events")
            elif int(type) == int(InteractionType.CHAT_MESSAGE):
                items = data.get("chat_messages")
            elif int(type) == int(InteractionType.EMAIL):
                items = data.get("emails")

        if items is None:
            items = (
                data.get("interactions")
                or data.get("events")
                or data.get("emails")
                or data.get("chat_messages")
                or data.get("data", [])
            )
        if not isinstance(items, list):
            items = []
        return V1PaginatedResponse[Interaction](
            data=[Interaction.model_validate(i) for i in items],
            next_page_token=data.get("next_page_token") or data.get("nextPageToken"),
        )

    def get(self, interaction_id: int, type: InteractionType) -> Interaction:
        """Get a single interaction by ID and type."""
        data = self._client.get(
            f"/interactions/{interaction_id}",
            params={"type": int(type)},
            v1=True,
        )
        return Interaction.model_validate(data)

    def create(self, data: InteractionCreate) -> Interaction:
        """Create a new interaction (manually logged)."""
        payload: dict[str, Any] = {
            "type": int(data.type),
            "person_ids": [int(p) for p in data.person_ids],
            "content": data.content,
            "date": data.date.isoformat(),
        }
        if data.direction is not None:
            payload["direction"] = int(data.direction)

        result = self._client.post("/interactions", json=payload, v1=True)
        return Interaction.model_validate(result)

    def update(
        self,
        interaction_id: int,
        type: InteractionType,
        data: InteractionUpdate,
    ) -> Interaction:
        """Update an interaction."""
        payload: dict[str, Any] = {"type": int(type)}
        if data.person_ids is not None:
            payload["person_ids"] = [int(p) for p in data.person_ids]
        if data.content is not None:
            payload["content"] = data.content
        if data.date is not None:
            payload["date"] = data.date.isoformat()
        if data.direction is not None:
            payload["direction"] = int(data.direction)

        result = self._client.put(f"/interactions/{interaction_id}", json=payload, v1=True)
        return Interaction.model_validate(result)

    def delete(self, interaction_id: int, type: InteractionType) -> bool:
        """Delete an interaction."""
        result = self._client.delete(
            f"/interactions/{interaction_id}",
            params={"type": int(type)},
            v1=True,
        )
        return bool(result.get("success", False))


# =============================================================================
# Field Service (V1 API)
# =============================================================================


class FieldService:
    """
    Service for managing custom fields.

    Use V2 /fields endpoints for reading field metadata.
    Use V1 for creating/deleting fields.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def list(
        self,
        *,
        list_id: ListId | None = None,
        entity_type: EntityType | None = None,
    ) -> list[FieldMetadata]:
        """
        Get fields (V1 API).

        For list/person/company field metadata, prefer the V2 read endpoints on the
        corresponding services when available (e.g., `client.lists.get_fields(...)`).
        """
        params: dict[str, Any] = {}
        if list_id:
            params["list_id"] = int(list_id)
        if entity_type is not None:
            params["entity_type"] = int(entity_type)

        data = self._client.get("/fields", params=params or None, v1=True)
        items = data.get("data", [])
        if not isinstance(items, list):
            items = []
        return [FieldMetadata.model_validate(f) for f in items]

    def create(self, data: FieldCreate) -> FieldMetadata:
        """Create a custom field."""
        payload: dict[str, Any] = {
            "name": data.name,
            "entity_type": int(data.entity_type),
            "value_type": int(data.value_type),
        }
        if data.list_id:
            payload["list_id"] = int(data.list_id)
        if data.allows_multiple:
            payload["allows_multiple"] = True
        if data.is_list_specific:
            payload["is_list_specific"] = True
        if data.is_required:
            payload["is_required"] = True

        result = self._client.post("/fields", json=payload, v1=True)

        # Invalidate field caches
        if self._client.cache:
            self._client.cache.invalidate_prefix("field")
            self._client.cache.invalidate_prefix("list_")
            self._client.cache.invalidate_prefix("person_fields")
            self._client.cache.invalidate_prefix("company_fields")

        return FieldMetadata.model_validate(result)

    def delete(self, field_id: FieldId) -> bool:
        """Delete a custom field."""
        numeric_id = field_id_to_v1_numeric(field_id)
        result = self._client.delete(f"/fields/{numeric_id}", v1=True)

        # Invalidate field caches
        if self._client.cache:
            self._client.cache.invalidate_prefix("field")
            self._client.cache.invalidate_prefix("list_")
            self._client.cache.invalidate_prefix("person_fields")
            self._client.cache.invalidate_prefix("company_fields")

        return bool(result.get("success", False))


# =============================================================================
# Field Value Service (V1 API)
# =============================================================================


class FieldValueService:
    """
    Service for managing field values.

    For list entry field values, prefer ListEntryService.update_field_value().
    Use this for global field values not tied to list entries.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def list(
        self,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
        list_entry_id: int | None = None,
    ) -> list[FieldValue]:
        """
        Get field values for an entity.

        Exactly one of the ID parameters must be provided.

        Raises:
            ValueError: If zero or multiple IDs are provided.
        """
        provided = [
            name
            for name, value in (
                ("person_id", person_id),
                ("organization_id", organization_id),
                ("opportunity_id", opportunity_id),
                ("list_entry_id", list_entry_id),
            )
            if value is not None
        ]
        if len(provided) != 1:
            joined = ", ".join(provided) if provided else "(none)"
            raise ValueError(
                "FieldValueService.list() requires exactly one ID parameter; "
                f"got {len(provided)}: {joined}"
            )

        params: dict[str, Any] = {}
        if person_id is not None:
            params["person_id"] = int(person_id)
        if organization_id is not None:
            params["organization_id"] = int(organization_id)
        if opportunity_id is not None:
            params["opportunity_id"] = int(opportunity_id)
        if list_entry_id is not None:
            params["list_entry_id"] = list_entry_id

        data = self._client.get("/field-values", params=params or None, v1=True)
        items = data.get("data", [])
        if not isinstance(items, list):
            items = []
        return [FieldValue.model_validate(v) for v in items]

    def create(self, data: FieldValueCreate) -> FieldValue:
        """Create a field value."""
        payload: dict[str, Any] = {
            "field_id": field_id_to_v1_numeric(data.field_id),
            "entity_id": data.entity_id,
            "value": data.value,
        }
        if data.list_entry_id:
            payload["list_entry_id"] = int(data.list_entry_id)

        result = self._client.post("/field-values", json=payload, v1=True)
        return FieldValue.model_validate(result)

    def update(self, field_value_id: FieldValueId, value: Any) -> FieldValue:
        """Update a field value."""
        result = self._client.put(
            f"/field-values/{field_value_id}",
            json={"value": value},
            v1=True,
        )
        return FieldValue.model_validate(result)

    def delete(self, field_value_id: FieldValueId) -> bool:
        """Delete a field value."""
        result = self._client.delete(f"/field-values/{field_value_id}", v1=True)
        return bool(result.get("success", False))


# =============================================================================
# Relationship Strength Service (V1 API)
# =============================================================================


class RelationshipStrengthService:
    """Service for querying relationship strengths."""

    def __init__(self, client: HTTPClient):
        self._client = client

    def get(
        self,
        external_id: PersonId,
        internal_id: UserId | None = None,
    ) -> list[RelationshipStrength]:
        """
        Get relationship strength(s) for an external person.

        Args:
            external_id: External person to query
            internal_id: Optional internal person for specific relationship

        Returns:
            List of relationship strengths (may be empty)
        """
        params: dict[str, Any] = {"external_id": int(external_id)}
        if internal_id:
            params["internal_id"] = int(internal_id)

        data = self._client.get("/relationships-strengths", params=params, v1=True)
        items = data.get("data", [])
        if not isinstance(items, list):
            items = []
        return [RelationshipStrength.model_validate(r) for r in items]


# =============================================================================
# Entity File Service (V1 API)
# =============================================================================


class EntityFileService:
    """Service for managing files attached to entities."""

    def __init__(self, client: HTTPClient):
        self._client = client

    def _validate_exactly_one_target(
        self,
        *,
        person_id: PersonId | None,
        organization_id: CompanyId | None,
        opportunity_id: OpportunityId | None,
    ) -> None:
        targets = [person_id, organization_id, opportunity_id]
        count = sum(1 for t in targets if t is not None)
        if count == 1:
            return
        if count == 0:
            raise ValueError(
                "Exactly one of person_id, organization_id, or opportunity_id is required"
            )
        raise ValueError(
            "Only one of person_id, organization_id, or opportunity_id may be provided"
        )

    def list(
        self,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> V1PaginatedResponse[EntityFile]:
        """Get files attached to an entity."""
        self._validate_exactly_one_target(
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )
        params: dict[str, Any] = {}
        if person_id:
            params["person_id"] = int(person_id)
        if organization_id:
            params["organization_id"] = int(organization_id)
        if opportunity_id:
            params["opportunity_id"] = int(opportunity_id)
        if page_size:
            params["page_size"] = page_size
        if page_token:
            params["page_token"] = page_token

        data = self._client.get("/entity-files", params=params or None, v1=True)
        items = (
            data.get("entity_files")
            or data.get("entityFiles")
            or data.get("files")
            or data.get("data", [])
        )
        if not isinstance(items, list):
            items = []
        return V1PaginatedResponse[EntityFile](
            data=[EntityFile.model_validate(f) for f in items],
            next_page_token=data.get("next_page_token") or data.get("nextPageToken"),
        )

    def get(self, file_id: FileId) -> EntityFile:
        """Get file metadata."""
        data = self._client.get(f"/entity-files/{file_id}", v1=True)
        return EntityFile.model_validate(data)

    def download(self, file_id: FileId) -> bytes:
        """Download file content."""
        return self._client.download_file(f"/entity-files/download/{file_id}", v1=True)

    def download_stream(
        self,
        file_id: FileId,
        *,
        chunk_size: int = 65_536,
        on_progress: ProgressCallback | None = None,
    ) -> Iterator[bytes]:
        """Stream-download file content in chunks."""
        return self._client.stream_download(
            f"/entity-files/download/{file_id}",
            v1=True,
            chunk_size=chunk_size,
            on_progress=on_progress,
        )

    def download_to(
        self,
        file_id: FileId,
        path: str | Path,
        *,
        overwrite: bool = False,
        chunk_size: int = 65_536,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        """
        Download a file to disk.

        Args:
            file_id: The entity file id
            path: Destination path
            overwrite: If False, raises FileExistsError when path exists
            chunk_size: Bytes per chunk

        Returns:
            The destination path
        """
        target = Path(path)
        if target.exists() and not overwrite:
            raise FileExistsError(str(target))

        with target.open("wb") as f:
            for chunk in self.download_stream(
                file_id,
                chunk_size=chunk_size,
                on_progress=on_progress,
            ):
                f.write(chunk)

        return target

    def upload(
        self,
        files: dict[str, Any],
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
    ) -> bool:
        """
        Upload files to an entity.

        Args:
            files: Dict of filename to file-like object
            person_id: Person to attach to
            organization_id: Company to attach to
            opportunity_id: Opportunity to attach to

        Returns:
            List of created file records
        """
        self._validate_exactly_one_target(
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )
        data: dict[str, Any] = {}
        if person_id:
            data["person_id"] = int(person_id)
        if organization_id:
            data["organization_id"] = int(organization_id)
        if opportunity_id:
            data["opportunity_id"] = int(opportunity_id)

        result = self._client.upload_file(
            "/entity-files",
            files=files,
            data=data,
            v1=True,
        )
        if "success" in result:
            return bool(result.get("success"))
        # If the API returns something else on success (e.g., created object),
        # treat any 2xx JSON response as success (4xx/5xx raise earlier).
        return True

    def upload_path(
        self,
        path: str | Path,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> bool:
        """
        Upload a file from disk.

        Notes:
        - Returns only a boolean because the API returns `{"success": true}` for uploads.
        - Progress reporting is best-effort for uploads (start/end only).
        """
        self._validate_exactly_one_target(
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )

        p = Path(path)
        upload_filename = filename or p.name
        guessed, _ = mimetypes.guess_type(upload_filename)
        final_content_type = content_type or guessed or "application/octet-stream"
        total = p.stat().st_size

        if on_progress:
            on_progress(0, total, phase="upload")

        with p.open("rb") as f:
            ok = self.upload(
                files={"file": (upload_filename, f, final_content_type)},
                person_id=person_id,
                organization_id=organization_id,
                opportunity_id=opportunity_id,
            )

        if on_progress:
            on_progress(total, total, phase="upload")

        return ok

    def upload_bytes(
        self,
        data: bytes,
        filename: str,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
        content_type: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> bool:
        """
        Upload in-memory bytes as a file.

        Notes:
        - Returns only a boolean because the API returns `{"success": true}` for uploads.
        - Progress reporting is best-effort for uploads (start/end only).
        """
        self._validate_exactly_one_target(
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )

        guessed, _ = mimetypes.guess_type(filename)
        final_content_type = content_type or guessed or "application/octet-stream"
        total = len(data)

        if on_progress:
            on_progress(0, total, phase="upload")

        ok = self.upload(
            files={"file": (filename, data, final_content_type)},
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )

        if on_progress:
            on_progress(total, total, phase="upload")

        return ok

    def all(
        self,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
    ) -> Iterator[EntityFile]:
        """Iterate through all files for an entity with automatic pagination."""
        self._validate_exactly_one_target(
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )

        page_token: str | None = None
        while True:
            page = self.list(
                person_id=person_id,
                organization_id=organization_id,
                opportunity_id=opportunity_id,
                page_token=page_token,
            )
            yield from page.data
            if not page.has_next:
                break
            page_token = page.next_page_token

    def iter(
        self,
        *,
        person_id: PersonId | None = None,
        organization_id: CompanyId | None = None,
        opportunity_id: OpportunityId | None = None,
    ) -> Iterator[EntityFile]:
        """Auto-paginate all files (alias for `all()`)."""
        return self.all(
            person_id=person_id,
            organization_id=organization_id,
            opportunity_id=opportunity_id,
        )


# =============================================================================
# Auth Service
# =============================================================================


class AuthService:
    """Service for authentication and rate limit info."""

    def __init__(self, client: HTTPClient):
        self._client = client

    def whoami(self) -> WhoAmI:
        """Get info about current user and API key."""
        # V2 also has this endpoint
        data = self._client.get("/auth/whoami")
        return WhoAmI.model_validate(data)

    def get_rate_limits(self) -> RateLimits:
        """Get current rate limit status."""
        data = self._client.get("/rate-limit", v1=True)
        return RateLimits.model_validate(data.get("rate", {}))
