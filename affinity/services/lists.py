"""
Lists and List Entries service.

Provides operations for managing lists (spreadsheets) and their entries (rows).
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from ..filters import FilterExpression
from ..models.entities import (
    AffinityList,
    FieldMetadata,
    FieldValues,
    ListCreate,
    ListEntry,
    ListEntryWithEntity,
    SavedView,
)
from ..models.pagination import (
    AsyncPageIterator,
    BatchOperationResponse,
    PageIterator,
    PaginatedResponse,
    PaginationInfo,
)
from ..models.types import (
    AnyFieldId,
    CompanyId,
    FieldType,
    ListEntryId,
    ListId,
    OpportunityId,
    PersonId,
    SavedViewId,
)

if TYPE_CHECKING:
    from ..clients.http import AsyncHTTPClient, HTTPClient


class ListService:
    """
    Service for managing lists.

    Lists are spreadsheet-like collections of people, companies, or opportunities.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    def entries(self, list_id: ListId) -> ListEntryService:
        """
        Get a ListEntryService for a specific list.

        This is the explicit path for retrieving "full row" data via list entries.
        """
        return ListEntryService(self._client, list_id)

    # =========================================================================
    # List Operations (V2 for read, V1 for write)
    # =========================================================================

    def list(self) -> PaginatedResponse[AffinityList]:
        """
        Get all lists accessible to you.

        Returns:
            Paginated list of lists (without field metadata)
        """
        data = self._client.get("/lists")

        return PaginatedResponse[AffinityList](
            data=[AffinityList.model_validate(list_item) for list_item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(self) -> Iterator[AffinityList]:
        """Iterate through all accessible lists."""

        def fetch_page(next_url: str | None) -> PaginatedResponse[AffinityList]:
            if next_url:
                data = self._client.get_url(next_url)
                return PaginatedResponse[AffinityList](
                    data=[
                        AffinityList.model_validate(list_item) for list_item in data.get("data", [])
                    ],
                    pagination=PaginationInfo.model_validate(data.get("pagination", {})),
                )
            return self.list()

        return PageIterator(fetch_page)

    def iter(self) -> Iterator[AffinityList]:
        """
        Auto-paginate all lists.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all()

    def get(self, list_id: ListId) -> AffinityList:
        """
        Get a single list by ID.

        Includes field metadata for the list.
        """
        data = self._client.get(f"/lists/{list_id}")
        return AffinityList.model_validate(data)

    def create(self, data: ListCreate) -> AffinityList:
        """
        Create a new list.

        Uses V1 API.
        """
        payload = {
            "name": data.name,
            "type": int(data.type),
            "is_public": data.is_public,
        }
        if data.owner_id:
            payload["owner_id"] = int(data.owner_id)
        if data.additional_permissions:
            payload["additional_permissions"] = [
                {"internal_person_id": int(p.internal_person_id), "role_id": int(p.role_id)}
                for p in data.additional_permissions
            ]

        result = self._client.post("/lists", json=payload, v1=True)

        # Invalidate cache
        if self._client.cache:
            self._client.cache.invalidate_prefix("list")

        return AffinityList.model_validate(result)

    # =========================================================================
    # Field Operations
    # =========================================================================

    def get_fields(
        self,
        list_id: ListId,
        *,
        field_types: Sequence[FieldType] | None = None,
    ) -> builtins.list[FieldMetadata]:
        """
        Get fields (columns) for a list.

        Includes list-specific, global, enriched, and relationship intelligence fields.
        Cached for performance.
        """
        params: dict[str, Any] = {}
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = self._client.get(
            f"/lists/{list_id}/fields",
            params=params or None,
            cache_key=f"list_{list_id}_fields:{','.join(field_types or [])}",
            cache_ttl=300,
        )

        return [FieldMetadata.model_validate(f) for f in data.get("data", [])]

    # =========================================================================
    # Saved View Operations
    # =========================================================================

    def get_saved_views(self, list_id: ListId) -> PaginatedResponse[SavedView]:
        """Get saved views for a list."""
        data = self._client.get(f"/lists/{list_id}/saved-views")

        return PaginatedResponse[SavedView](
            data=[SavedView.model_validate(v) for v in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def get_saved_view(self, list_id: ListId, view_id: SavedViewId) -> SavedView:
        """Get a single saved view."""
        data = self._client.get(f"/lists/{list_id}/saved-views/{view_id}")
        return SavedView.model_validate(data)


class ListEntryService:
    """
    Service for managing list entries (rows).

    List entries connect entities (people, companies, opportunities) to lists
    and hold list-specific field values.
    """

    def __init__(self, client: HTTPClient, list_id: ListId):
        self._client = client
        self._list_id = list_id

    def _all_entity_list_entries_v2(self, path: str) -> builtins.list[ListEntry]:
        """
        Fetch all list entries for a single entity across all lists (V2 API).

        Used for list membership helpers to avoid enumerating an entire list.
        """
        entries: builtins.list[ListEntry] = []
        data = self._client.get(path)

        while True:
            entries.extend(ListEntry.model_validate(item) for item in data.get("data", []))
            pagination = PaginationInfo.model_validate(data.get("pagination", {}))
            if not pagination.next_url:
                break
            data = self._client.get_url(pagination.next_url)

        return entries

    # =========================================================================
    # Read Operations (V2 API)
    # =========================================================================

    def list(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
    ) -> PaginatedResponse[ListEntryWithEntity]:
        """
        Get list entries with entity data and field values.

        Args:
            field_ids: Specific field IDs to include
            field_types: Field types to include
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
            limit: Maximum results per page

        Returns:
            Paginated list entries with entity data
        """
        params: dict[str, Any] = {}
        if field_ids:
            params["fieldIds"] = [str(field_id) for field_id in field_ids]
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]
        if filter is not None:
            filter_text = str(filter).strip()
            if filter_text:
                params["filter"] = filter_text
        if limit:
            params["limit"] = limit

        data = self._client.get(
            f"/lists/{self._list_id}/list-entries",
            params=params or None,
        )

        return PaginatedResponse[ListEntryWithEntity](
            data=[ListEntryWithEntity.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[ListEntryWithEntity]:
        """Iterate through all list entries with automatic pagination."""

        def fetch_page(next_url: str | None) -> PaginatedResponse[ListEntryWithEntity]:
            if next_url:
                data = self._client.get_url(next_url)
                return PaginatedResponse[ListEntryWithEntity](
                    data=[ListEntryWithEntity.model_validate(e) for e in data.get("data", [])],
                    pagination=PaginationInfo.model_validate(data.get("pagination", {})),
                )
            return self.list(
                field_ids=field_ids,
                field_types=field_types,
                filter=filter,
            )

        return PageIterator(fetch_page)

    def iter(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[ListEntryWithEntity]:
        """
        Auto-paginate all list entries.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(field_ids=field_ids, field_types=field_types, filter=filter)

    def get(self, entry_id: ListEntryId) -> ListEntryWithEntity:
        """Get a single list entry by ID."""
        data = self._client.get(f"/lists/{self._list_id}/list-entries/{entry_id}")
        return ListEntryWithEntity.model_validate(data)

    def from_saved_view(
        self,
        view_id: SavedViewId,
        *,
        limit: int | None = None,
    ) -> PaginatedResponse[ListEntryWithEntity]:
        """
        Get list entries from a saved view.

        Respects the view's field selection and filters (but not sorts).
        """
        params: dict[str, Any] = {}
        if limit:
            params["limit"] = limit

        data = self._client.get(
            f"/lists/{self._list_id}/saved-views/{view_id}/list-entries",
            params=params or None,
        )

        return PaginatedResponse[ListEntryWithEntity](
            data=[ListEntryWithEntity.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    # =========================================================================
    # Write Operations (V1 API for create/delete, V2 for field updates)
    # =========================================================================

    # -------------------------------------------------------------------------
    # Membership helpers (V2 for read, V1 for insert)
    # -------------------------------------------------------------------------

    def find_person(self, person_id: PersonId) -> ListEntry | None:
        """
        Return the first list entry for this person on this list (or None).

        Notes:
        - Affinity lists can contain duplicates. This returns the first match in
          the server-provided order. Use `find_all_person()` to surface all matches.
        """
        entries = self.find_all_person(person_id)
        return entries[0] if entries else None

    def find_all_person(self, person_id: PersonId) -> builtins.list[ListEntry]:
        """
        Return all list entries for this person on this list (may be empty).

        Affinity allows the same entity to appear multiple times on a list.
        """
        all_entries = self._all_entity_list_entries_v2(f"/persons/{person_id}/list-entries")
        return [entry for entry in all_entries if entry.list_id == self._list_id]

    def ensure_person(
        self,
        person_id: PersonId,
        *,
        creator_id: int | None = None,
    ) -> ListEntry:
        """
        Ensure a person is on this list (idempotent by default).

        Returns:
            The first existing list entry if present; otherwise creates a new one.

        Notes:
        - This method performs an existence check to avoid accidental duplicates.
          To intentionally create duplicates, call `add_person()` directly.
        """
        existing = self.find_person(person_id)
        if existing is not None:
            return existing
        return self.add_person(person_id, creator_id=creator_id)

    def find_company(self, company_id: CompanyId) -> ListEntry | None:
        """
        Return the first list entry for this company on this list (or None).

        Notes:
        - Affinity lists can contain duplicates. This returns the first match in
          the server-provided order. Use `find_all_company()` to surface all matches.
        """
        entries = self.find_all_company(company_id)
        return entries[0] if entries else None

    def find_all_company(self, company_id: CompanyId) -> builtins.list[ListEntry]:
        """
        Return all list entries for this company on this list (may be empty).

        Affinity allows the same entity to appear multiple times on a list.
        """
        all_entries = self._all_entity_list_entries_v2(f"/companies/{company_id}/list-entries")
        return [entry for entry in all_entries if entry.list_id == self._list_id]

    def ensure_company(
        self,
        company_id: CompanyId,
        *,
        creator_id: int | None = None,
    ) -> ListEntry:
        """
        Ensure a company is on this list (idempotent by default).

        Returns:
            The first existing list entry if present; otherwise creates a new one.

        Notes:
        - This method performs an existence check to avoid accidental duplicates.
          To intentionally create duplicates, call `add_company()` directly.
        """
        existing = self.find_company(company_id)
        if existing is not None:
            return existing
        return self.add_company(company_id, creator_id=creator_id)

    def add_person(
        self,
        person_id: PersonId,
        *,
        creator_id: int | None = None,
    ) -> ListEntry:
        """Add a person to this list."""
        return self._create_entry(int(person_id), creator_id)

    def add_company(
        self,
        company_id: CompanyId,
        *,
        creator_id: int | None = None,
    ) -> ListEntry:
        """Add a company to this list."""
        return self._create_entry(int(company_id), creator_id)

    def add_opportunity(
        self,
        opportunity_id: OpportunityId,
        *,
        creator_id: int | None = None,
    ) -> ListEntry:
        """Add an opportunity to this list."""
        return self._create_entry(int(opportunity_id), creator_id)

    def _create_entry(
        self,
        entity_id: int,
        creator_id: int | None = None,
    ) -> ListEntry:
        """Internal method to create a list entry."""
        payload: dict[str, Any] = {"entity_id": entity_id}
        if creator_id:
            payload["creator_id"] = creator_id

        result = self._client.post(
            f"/lists/{self._list_id}/list-entries",
            json=payload,
            v1=True,
        )

        return ListEntry.model_validate(result)

    def delete(self, entry_id: ListEntryId) -> bool:
        """
        Remove a list entry (row) from the list.

        Note: This only removes the entry from the list, not the entity itself.
        """
        result = self._client.delete(
            f"/lists/{self._list_id}/list-entries/{entry_id}",
            v1=True,
        )
        return bool(result.get("success", False))

    # =========================================================================
    # Field Value Operations (V2 API)
    # =========================================================================

    def get_field_values(
        self,
        entry_id: ListEntryId,
    ) -> FieldValues:
        """Get all field values for a list entry."""
        data = self._client.get(f"/lists/{self._list_id}/list-entries/{entry_id}/fields")
        values = data.get("data", {})
        if isinstance(values, dict):
            return FieldValues.model_validate(values)
        return FieldValues.model_validate({})

    def get_field_value(
        self,
        entry_id: ListEntryId,
        field_id: AnyFieldId,
    ) -> Any:
        """Get a single field value."""
        data = self._client.get(f"/lists/{self._list_id}/list-entries/{entry_id}/fields/{field_id}")
        return data.get("value")

    def update_field_value(
        self,
        entry_id: ListEntryId,
        field_id: AnyFieldId,
        value: Any,
    ) -> FieldValues:
        """
        Update a single field value on a list entry.

        Args:
            entry_id: The list entry
            field_id: The field to update
            value: New value (type depends on field type)

        Returns:
            Updated field value data
        """
        result = self._client.post(
            f"/lists/{self._list_id}/list-entries/{entry_id}/fields/{field_id}",
            json={"value": value},
        )
        return FieldValues.model_validate(result)

    def batch_update_fields(
        self,
        entry_id: ListEntryId,
        updates: dict[AnyFieldId, Any],
    ) -> BatchOperationResponse:
        """
        Update multiple field values at once.

        More efficient than individual updates for multiple fields.

        Args:
            entry_id: The list entry
            updates: Dict mapping field IDs to new values

        Returns:
            Batch operation response with success/failure per field
        """
        operations = [
            {"fieldId": str(field_id), "value": value} for field_id, value in updates.items()
        ]

        result = self._client.patch(
            f"/lists/{self._list_id}/list-entries/{entry_id}/fields",
            json={"operations": operations},
        )

        return BatchOperationResponse.model_validate(result)


class AsyncListService:
    """Async list operations (TR-009)."""

    def __init__(self, client: AsyncHTTPClient):
        self._client = client

    def entries(self, list_id: ListId) -> AsyncListEntryService:
        """
        Get an AsyncListEntryService for a specific list.

        This is the explicit path for retrieving "full row" data via list entries.
        """
        return AsyncListEntryService(self._client, list_id)

    async def list(self) -> PaginatedResponse[AffinityList]:
        """
        Get all lists accessible to you.

        Returns:
            Paginated list of lists (without field metadata)
        """
        data = await self._client.get("/lists")
        return PaginatedResponse[AffinityList](
            data=[AffinityList.model_validate(list_item) for list_item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(self) -> AsyncIterator[AffinityList]:
        """Iterate through all accessible lists."""

        async def fetch_page(next_url: str | None) -> PaginatedResponse[AffinityList]:
            if next_url:
                data = await self._client.get_url(next_url)
                return PaginatedResponse[AffinityList](
                    data=[
                        AffinityList.model_validate(list_item) for list_item in data.get("data", [])
                    ],
                    pagination=PaginationInfo.model_validate(data.get("pagination", {})),
                )
            return await self.list()

        return AsyncPageIterator(fetch_page)

    def iter(self) -> AsyncIterator[AffinityList]:
        """
        Auto-paginate all lists.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all()

    async def get(self, list_id: ListId) -> AffinityList:
        """
        Get a single list by ID.

        Includes field metadata for the list.
        """
        data = await self._client.get(f"/lists/{list_id}")
        return AffinityList.model_validate(data)


class AsyncListEntryService:
    """Async list entry operations (V2 read paths only) (TR-009)."""

    def __init__(self, client: AsyncHTTPClient, list_id: ListId):
        self._client = client
        self._list_id = list_id

    async def _all_entity_list_entries_v2(self, path: str) -> builtins.list[ListEntry]:
        """
        Fetch all list entries for a single entity across all lists (V2 API).

        Used for list membership helpers to avoid enumerating an entire list.
        """
        entries: builtins.list[ListEntry] = []
        data = await self._client.get(path)

        while True:
            entries.extend(ListEntry.model_validate(item) for item in data.get("data", []))
            pagination = PaginationInfo.model_validate(data.get("pagination", {}))
            if not pagination.next_url:
                break
            data = await self._client.get_url(pagination.next_url)

        return entries

    async def list(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
    ) -> PaginatedResponse[ListEntryWithEntity]:
        """
        Get list entries with entity data and field values.

        Args:
            field_ids: Specific field IDs to include
            field_types: Field types to include
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
            limit: Maximum results per page

        Returns:
            Paginated list entries with entity data
        """
        params: dict[str, Any] = {}
        if field_ids:
            params["fieldIds"] = [str(field_id) for field_id in field_ids]
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]
        if filter is not None:
            filter_text = str(filter).strip()
            if filter_text:
                params["filter"] = filter_text
        if limit:
            params["limit"] = limit

        data = await self._client.get(
            f"/lists/{self._list_id}/list-entries",
            params=params or None,
        )
        return PaginatedResponse[ListEntryWithEntity](
            data=[ListEntryWithEntity.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> AsyncIterator[ListEntryWithEntity]:
        """Iterate through all list entries with automatic pagination."""

        async def fetch_page(next_url: str | None) -> PaginatedResponse[ListEntryWithEntity]:
            if next_url:
                data = await self._client.get_url(next_url)
                return PaginatedResponse[ListEntryWithEntity](
                    data=[ListEntryWithEntity.model_validate(e) for e in data.get("data", [])],
                    pagination=PaginationInfo.model_validate(data.get("pagination", {})),
                )
            return await self.list(field_ids=field_ids, field_types=field_types, filter=filter)

        return AsyncPageIterator(fetch_page)

    def iter(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> AsyncIterator[ListEntryWithEntity]:
        """
        Auto-paginate all list entries.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(field_ids=field_ids, field_types=field_types, filter=filter)

    # -------------------------------------------------------------------------
    # Membership helpers (V2 for read only)
    # -------------------------------------------------------------------------

    async def find_person(self, person_id: PersonId) -> ListEntry | None:
        """
        Return the first list entry for this person on this list (or None).

        Notes:
        - Affinity lists can contain duplicates. This returns the first match in
          the server-provided order. Use `find_all_person()` to surface all matches.
        """
        entries = await self.find_all_person(person_id)
        return entries[0] if entries else None

    async def find_all_person(self, person_id: PersonId) -> builtins.list[ListEntry]:
        """
        Return all list entries for this person on this list (may be empty).

        Affinity allows the same entity to appear multiple times on a list.
        """
        all_entries = await self._all_entity_list_entries_v2(f"/persons/{person_id}/list-entries")
        return [entry for entry in all_entries if entry.list_id == self._list_id]

    async def find_company(self, company_id: CompanyId) -> ListEntry | None:
        """
        Return the first list entry for this company on this list (or None).

        Notes:
        - Affinity lists can contain duplicates. This returns the first match in
          the server-provided order. Use `find_all_company()` to surface all matches.
        """
        entries = await self.find_all_company(company_id)
        return entries[0] if entries else None

    async def find_all_company(self, company_id: CompanyId) -> builtins.list[ListEntry]:
        """
        Return all list entries for this company on this list (may be empty).

        Affinity allows the same entity to appear multiple times on a list.
        """
        all_entries = await self._all_entity_list_entries_v2(
            f"/companies/{company_id}/list-entries"
        )
        return [entry for entry in all_entries if entry.list_id == self._list_id]
