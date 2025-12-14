"""
Opportunity service.

Opportunities can be retrieved via v2 endpoints, but full "row" data (fields)
is available via list entries.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from ..models.entities import (
    Opportunity,
    OpportunityCreate,
)
from ..models.pagination import AsyncPageIterator, PageIterator, PaginatedResponse, PaginationInfo
from ..models.types import (
    OpportunityId,
)

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
    # Read Operations (V2 API)
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

    def list(
        self,
        *,
        limit: int | None = None,
    ) -> PaginatedResponse[Opportunity]:
        """
        List all opportunities.

        Returns the v2 opportunity representation (which may be partial).
        For full opportunity row data, use list entries explicitly.
        """
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit

        data = self._client.get("/opportunities", params=params or None)
        return PaginatedResponse[Opportunity](
            data=[Opportunity.model_validate(item) for item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

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
        data = await self._client.get(f"/opportunities/{opportunity_id}")
        return Opportunity.model_validate(data)

    async def list(self, *, limit: int | None = None) -> PaginatedResponse[Opportunity]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        data = await self._client.get("/opportunities", params=params or None)
        return PaginatedResponse[Opportunity](
            data=[Opportunity.model_validate(item) for item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(self) -> AsyncIterator[Opportunity]:
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
        return self.all()

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
