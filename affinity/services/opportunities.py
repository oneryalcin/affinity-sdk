"""
Opportunity service.

Opportunities can be retrieved via v2 endpoints, but full "row" data (fields)
is available via list entries.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from ..models.entities import (
    Opportunity,
    OpportunityCreate,
    OpportunityUpdate,
)
from ..models.pagination import AsyncPageIterator, PageIterator, PaginatedResponse, PaginationInfo
from ..models.types import ListId, OpportunityId
from .lists import AsyncListEntryService, ListEntryService

if TYPE_CHECKING:
    from ..clients.http import AsyncHTTPClient, HTTPClient


class OpportunityService:
    """
    Service for managing opportunities.

    Notes:
    - V2 opportunity endpoints may return partial representations (e.g. name and
      listId only). The SDK does not perform hidden follow-up calls to "complete"
      an opportunity.
    - For full opportunity row data (including list fields), use list entries
      explicitly via `client.lists.entries(list_id)`.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

    # =========================================================================
    # Read Operations (V2 API by default)
    # =========================================================================

    def get(self, opportunity_id: OpportunityId) -> Opportunity:
        """
        Get a single opportunity by ID.

        Args:
            opportunity_id: The opportunity ID

        Returns:
            The opportunity representation returned by v2 (may be partial).
        """
        data = self._client.get(f"/opportunities/{opportunity_id}")
        return Opportunity.model_validate(data)

    def get_details(self, opportunity_id: OpportunityId) -> Opportunity:
        """
        Get a single opportunity by ID with a more complete representation.

        Includes association IDs and (when present) list entries, which are not
        always included in the default `get()` response.
        """
        # Uses the v1 endpoint because it returns a fuller payload (including
        # association IDs and, when present, list entries).
        data = self._client.get(f"/opportunities/{opportunity_id}", v1=True)
        return Opportunity.model_validate(data)

    def list(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[Opportunity]:
        """
        List all opportunities.

        Args:
            limit: Maximum number of results per page
            cursor: Cursor to resume pagination (opaque; obtained from prior responses)

        Returns the v2 opportunity representation (which may be partial).
        For full opportunity row data, use list entries explicitly.
        """
        if cursor is not None:
            if limit is not None:
                raise ValueError(
                    "Cannot combine 'cursor' with other parameters; cursor encodes all query "
                    "context. Start a new pagination sequence without a cursor to change "
                    "parameters."
                )
            data = self._client.get_url(cursor)
        else:
            params: dict[str, Any] = {}
            if limit is not None:
                params["limit"] = limit
            data = self._client.get("/opportunities", params=params or None)

        return PaginatedResponse[Opportunity](
            data=[Opportunity.model_validate(item) for item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def pages(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Iterator[PaginatedResponse[Opportunity]]:
        """
        Iterate opportunity pages (not items), yielding `PaginatedResponse[Opportunity]`.

        This is useful for ETL scripts that want checkpoint/resume via `page.next_cursor`.
        """
        if cursor is not None and limit is not None:
            raise ValueError(
                "Cannot combine 'cursor' with other parameters; cursor encodes all query context. "
                "Start a new pagination sequence without a cursor to change parameters."
            )
        requested_cursor = cursor
        page = self.list(cursor=cursor) if cursor is not None else self.list(limit=limit)
        while True:
            yield page
            if not page.has_next:
                return
            next_cursor = page.next_cursor
            if next_cursor is None or next_cursor == requested_cursor:
                return
            requested_cursor = next_cursor
            page = self.list(cursor=next_cursor)

    def all(self) -> Iterator[Opportunity]:
        """Iterate through all opportunities with automatic pagination."""

        def fetch_page(next_url: str | None) -> PaginatedResponse[Opportunity]:
            if next_url:
                data = self._client.get_url(next_url)
                return PaginatedResponse[Opportunity](
                    data=[Opportunity.model_validate(item) for item in data.get("data", [])],
                    pagination=PaginationInfo.model_validate(data.get("pagination", {})),
                )
            return self.list()

        return PageIterator(fetch_page)

    def iter(self) -> Iterator[Opportunity]:
        """
        Auto-paginate all opportunities.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all()

    def resolve(
        self,
        *,
        name: str,
        list_id: ListId,
        limit: int | None = None,
    ) -> Opportunity | None:
        """
        Find a single opportunity by exact name within a specific list.

        Notes:
        - Opportunities are list-scoped; a list id is required.
        - This iterates list-entry pages client-side (no dedicated search endpoint).
        - If multiple matches exist, returns the first match in server-provided order.
        """
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty")
        name_lower = name.lower()

        entries = ListEntryService(self._client, list_id)
        for page in entries.pages(limit=limit):
            for entry in page.data:
                entity = entry.entity
                if isinstance(entity, Opportunity) and entity.name.lower() == name_lower:
                    return entity
        return None

    def resolve_all(
        self,
        *,
        name: str,
        list_id: ListId,
        limit: int | None = None,
    ) -> builtins.list[Opportunity]:
        """
        Find all opportunities matching a name within a specific list.

        Notes:
        - Opportunities are list-scoped; a list id is required.
        - This iterates list-entry pages client-side (no dedicated search endpoint).
        """
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty")
        name_lower = name.lower()
        matches: builtins.list[Opportunity] = []

        entries = ListEntryService(self._client, list_id)
        for page in entries.pages(limit=limit):
            for entry in page.data:
                entity = entry.entity
                if isinstance(entity, Opportunity) and entity.name.lower() == name_lower:
                    matches.append(entity)
        return matches

    # =========================================================================
    # Write Operations (V1 API)
    # =========================================================================

    def create(self, data: OpportunityCreate) -> Opportunity:
        """
        Create a new opportunity.

        The opportunity will be added to the specified list.

        Args:
            data: Opportunity creation data including list_id and name

        Returns:
            The created opportunity
        """
        payload: dict[str, Any] = {
            "name": data.name,
            "list_id": int(data.list_id),
        }
        if data.person_ids:
            payload["person_ids"] = [int(p) for p in data.person_ids]
        if data.organization_ids:
            payload["organization_ids"] = [int(o) for o in data.organization_ids]

        result = self._client.post("/opportunities", json=payload, v1=True)
        return Opportunity.model_validate(result)

    def update(self, opportunity_id: OpportunityId, data: OpportunityUpdate) -> Opportunity:
        """
        Update an existing opportunity.

        Note: When provided, `person_ids` and `organization_ids` replace the existing
        values. To add or remove associations safely, pass the full desired arrays.
        """
        payload: dict[str, Any] = {}
        if data.name is not None:
            payload["name"] = data.name
        if data.person_ids is not None:
            payload["person_ids"] = [int(p) for p in data.person_ids]
        if data.organization_ids is not None:
            payload["organization_ids"] = [int(o) for o in data.organization_ids]

        # Uses the v1 endpoint; its PUT semantics replace association arrays.
        result = self._client.put(f"/opportunities/{opportunity_id}", json=payload, v1=True)
        return Opportunity.model_validate(result)

    def delete(self, opportunity_id: OpportunityId) -> bool:
        """
        Delete an opportunity.

        This removes the opportunity and all associated list entries.

        Args:
            opportunity_id: The opportunity to delete

        Returns:
            True if successful
        """
        result = self._client.delete(f"/opportunities/{opportunity_id}", v1=True)
        return bool(result.get("success", False))


class AsyncOpportunityService:
    """Async version of OpportunityService (TR-009)."""

    def __init__(self, client: AsyncHTTPClient):
        self._client = client

    async def get(self, opportunity_id: OpportunityId) -> Opportunity:
        """
        Get a single opportunity by ID.

        Args:
            opportunity_id: The opportunity ID

        Returns:
            The opportunity representation returned by v2 (may be partial).
        """
        data = await self._client.get(f"/opportunities/{opportunity_id}")
        return Opportunity.model_validate(data)

    async def get_details(self, opportunity_id: OpportunityId) -> Opportunity:
        """
        Get a single opportunity by ID with a more complete representation.

        Includes association IDs and (when present) list entries, which are not
        always included in the default `get()` response.
        """
        # Uses the v1 endpoint because it returns a fuller payload (including
        # association IDs and, when present, list entries).
        data = await self._client.get(f"/opportunities/{opportunity_id}", v1=True)
        return Opportunity.model_validate(data)

    async def list(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[Opportunity]:
        """
        List all opportunities.

        Args:
            limit: Maximum number of results per page
            cursor: Cursor to resume pagination (opaque; obtained from prior responses)

        Returns the v2 opportunity representation (which may be partial).
        For full opportunity row data, use list entries explicitly.
        """
        if cursor is not None:
            if limit is not None:
                raise ValueError(
                    "Cannot combine 'cursor' with other parameters; cursor encodes all query "
                    "context. Start a new pagination sequence without a cursor to change "
                    "parameters."
                )
            data = await self._client.get_url(cursor)
        else:
            params: dict[str, Any] = {}
            if limit is not None:
                params["limit"] = limit
            data = await self._client.get("/opportunities", params=params or None)

        return PaginatedResponse[Opportunity](
            data=[Opportunity.model_validate(item) for item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    async def pages(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncIterator[PaginatedResponse[Opportunity]]:
        """
        Iterate opportunity pages (not items), yielding `PaginatedResponse[Opportunity]`.

        This is useful for ETL scripts that want checkpoint/resume via `page.next_cursor`.
        """
        if cursor is not None and limit is not None:
            raise ValueError(
                "Cannot combine 'cursor' with other parameters; cursor encodes all query context. "
                "Start a new pagination sequence without a cursor to change parameters."
            )
        requested_cursor = cursor
        page = (
            await self.list(cursor=cursor) if cursor is not None else await self.list(limit=limit)
        )
        while True:
            yield page
            if not page.has_next:
                return
            next_cursor = page.next_cursor
            if next_cursor is None or next_cursor == requested_cursor:
                return
            requested_cursor = next_cursor
            page = await self.list(cursor=next_cursor)

    def all(self) -> AsyncIterator[Opportunity]:
        """Iterate through all opportunities with automatic pagination."""

        async def fetch_page(next_url: str | None) -> PaginatedResponse[Opportunity]:
            if next_url:
                data = await self._client.get_url(next_url)
                return PaginatedResponse[Opportunity](
                    data=[Opportunity.model_validate(item) for item in data.get("data", [])],
                    pagination=PaginationInfo.model_validate(data.get("pagination", {})),
                )
            return await self.list()

        return AsyncPageIterator(fetch_page)

    def iter(self) -> AsyncIterator[Opportunity]:
        """
        Auto-paginate all opportunities.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all()

    async def resolve(
        self,
        *,
        name: str,
        list_id: ListId,
        limit: int | None = None,
    ) -> Opportunity | None:
        """
        Find a single opportunity by exact name within a specific list.

        Notes:
        - Opportunities are list-scoped; a list id is required.
        - This iterates list-entry pages client-side (no dedicated search endpoint).
        - If multiple matches exist, returns the first match in server-provided order.
        """
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty")
        name_lower = name.lower()

        entries = AsyncListEntryService(self._client, list_id)
        async for page in entries.pages(limit=limit):
            for entry in page.data:
                entity = entry.entity
                if isinstance(entity, Opportunity) and entity.name.lower() == name_lower:
                    return entity
        return None

    async def resolve_all(
        self,
        *,
        name: str,
        list_id: ListId,
        limit: int | None = None,
    ) -> builtins.list[Opportunity]:
        """
        Find all opportunities matching a name within a specific list.

        Notes:
        - Opportunities are list-scoped; a list id is required.
        - This iterates list-entry pages client-side (no dedicated search endpoint).
        """
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty")
        name_lower = name.lower()
        matches: builtins.list[Opportunity] = []

        entries = AsyncListEntryService(self._client, list_id)
        async for page in entries.pages(limit=limit):
            for entry in page.data:
                entity = entry.entity
                if isinstance(entity, Opportunity) and entity.name.lower() == name_lower:
                    matches.append(entity)
        return matches

    # =========================================================================
    # Write Operations (V1 API)
    # =========================================================================

    async def create(self, data: OpportunityCreate) -> Opportunity:
        """
        Create a new opportunity.

        The opportunity will be added to the specified list.

        Args:
            data: Opportunity creation data including list_id and name

        Returns:
            The created opportunity
        """
        payload: dict[str, Any] = {
            "name": data.name,
            "list_id": int(data.list_id),
        }
        if data.person_ids:
            payload["person_ids"] = [int(p) for p in data.person_ids]
        if data.organization_ids:
            payload["organization_ids"] = [int(o) for o in data.organization_ids]

        result = await self._client.post("/opportunities", json=payload, v1=True)
        return Opportunity.model_validate(result)

    async def update(self, opportunity_id: OpportunityId, data: OpportunityUpdate) -> Opportunity:
        """
        Update an existing opportunity.

        Note: When provided, `person_ids` and `organization_ids` replace the existing
        values. To add or remove associations safely, pass the full desired arrays.
        """
        payload: dict[str, Any] = {}
        if data.name is not None:
            payload["name"] = data.name
        if data.person_ids is not None:
            payload["person_ids"] = [int(p) for p in data.person_ids]
        if data.organization_ids is not None:
            payload["organization_ids"] = [int(o) for o in data.organization_ids]

        # Uses the v1 endpoint; its PUT semantics replace association arrays.
        result = await self._client.put(f"/opportunities/{opportunity_id}", json=payload, v1=True)
        return Opportunity.model_validate(result)

    async def delete(self, opportunity_id: OpportunityId) -> bool:
        """
        Delete an opportunity.

        This removes the opportunity and all associated list entries.

        Args:
            opportunity_id: The opportunity to delete

        Returns:
            True if successful
        """
        result = await self._client.delete(f"/opportunities/{opportunity_id}", v1=True)
        return bool(result.get("success", False))
