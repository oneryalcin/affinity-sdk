"""
Company (Organization) service.

Provides operations for managing companies/organizations in Affinity.
Uses V2 API for reading, V1 API for writing.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from ..exceptions import BetaEndpointDisabledError
from ..filters import FilterExpression
from ..models.entities import (
    Company,
    CompanyCreate,
    CompanyUpdate,
    FieldMetadata,
    ListEntry,
    ListSummary,
)
from ..models.pagination import (
    AsyncPageIterator,
    PageIterator,
    PaginatedResponse,
    PaginationInfo,
    V1PaginatedResponse,
)
from ..models.secondary import MergeTask
from ..models.types import AnyFieldId, CompanyId, FieldType

if TYPE_CHECKING:
    from ..clients.http import AsyncHTTPClient, HTTPClient


class CompanyService:
    """
    Service for managing companies (organizations).

    Note: Companies are called Organizations in the V1 API. This service
    uses V2 terminology throughout but routes to V1 for create/update/delete.
    """

    def __init__(self, client: HTTPClient):
        self._client = client

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
    ) -> PaginatedResponse[Company]:
        """
        Get a page of companies.

        Args:
            field_ids: Specific field IDs to include in response
            field_types: Field types to include (e.g., ["enriched", "global"])
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
                (e.g., `F.field("domain").contains("acme")`)
            limit: Maximum number of results (API default: 100)

        Returns:
            Paginated response with companies
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

        data = self._client.get("/companies", params=params or None)

        return PaginatedResponse[Company](
            data=[Company.model_validate(c) for c in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[Company]:
        """
        Iterate through all companies with automatic pagination.

        Args:
            field_ids: Specific field IDs to include
            field_types: Field types to include
            filter: V2 filter expression

        Yields:
            Company objects
        """

        def fetch_page(next_url: str | None) -> PaginatedResponse[Company]:
            if next_url:
                data = self._client.get_url(next_url)
            else:
                return self.list(
                    field_ids=field_ids,
                    field_types=field_types,
                    filter=filter,
                )
            return PaginatedResponse[Company](
                data=[Company.model_validate(c) for c in data.get("data", [])],
                pagination=PaginationInfo.model_validate(data.get("pagination", {})),
            )

        return PageIterator(fetch_page)

    def iter(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[Company]:
        """
        Auto-paginate all companies.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(field_ids=field_ids, field_types=field_types, filter=filter)

    def get(
        self,
        company_id: CompanyId,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
    ) -> Company:
        """
        Get a single company by ID.

        Args:
            company_id: The company ID
            field_ids: Specific field IDs to include
            field_types: Field types to include

        Returns:
            Company object with requested field data
        """
        params: dict[str, Any] = {}
        if field_ids:
            params["fieldIds"] = [str(field_id) for field_id in field_ids]
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = self._client.get(
            f"/companies/{company_id}",
            params=params or None,
        )
        return Company.model_validate(data)

    def get_list_entries(
        self,
        company_id: CompanyId,
    ) -> PaginatedResponse[ListEntry]:
        """
        Get all list entries for a company across all lists.

        Returns comprehensive field data for each list entry.
        """
        data = self._client.get(f"/companies/{company_id}/list-entries")

        return PaginatedResponse[ListEntry](
            data=[ListEntry.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def get_lists(
        self,
        company_id: CompanyId,
    ) -> PaginatedResponse[ListSummary]:
        """Get all lists that contain this company."""
        data = self._client.get(f"/companies/{company_id}/lists")

        return PaginatedResponse[ListSummary](
            data=[ListSummary.model_validate(item) for item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def get_fields(
        self,
        *,
        field_types: Sequence[FieldType] | None = None,
    ) -> builtins.list[FieldMetadata]:
        """
        Get metadata about company fields.

        Cached for performance.
        """
        params: dict[str, Any] = {}
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = self._client.get(
            "/companies/fields",
            params=params or None,
            cache_key=f"company_fields:{','.join(field_types or [])}",
            cache_ttl=300,
        )

        return [FieldMetadata.model_validate(f) for f in data.get("data", [])]

    # =========================================================================
    # Search (V1 API)
    # =========================================================================

    def search(
        self,
        term: str,
        *,
        with_interaction_dates: bool = False,
        with_interaction_persons: bool = False,
        with_opportunities: bool = False,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> V1PaginatedResponse[Company]:
        """
        Search for companies by name or domain.

        Uses V1 API for search functionality not available in V2.

        Args:
            term: Search term (name or domain)
            with_interaction_dates: Include interaction date data
            with_interaction_persons: Include persons for interactions
            with_opportunities: Include associated opportunity IDs
            page_size: Results per page (max 500)
            page_token: Pagination token

        Returns:
            Dict with 'organizations' and 'next_page_token'
        """
        params: dict[str, Any] = {"term": term}
        if with_interaction_dates:
            params["with_interaction_dates"] = True
        if with_interaction_persons:
            params["with_interaction_persons"] = True
        if with_opportunities:
            params["with_opportunities"] = True
        if page_size:
            params["page_size"] = page_size
        if page_token:
            params["page_token"] = page_token

        data = self._client.get("/organizations", params=params, v1=True)
        items = [Company.model_validate(o) for o in data.get("organizations", [])]
        return V1PaginatedResponse[Company](
            data=items,
            next_page_token=data.get("next_page_token"),
        )

    def resolve(
        self,
        *,
        domain: str | None = None,
        name: str | None = None,
    ) -> Company | None:
        """
        Find a single company by domain or name.

        This is a convenience helper that searches and returns the first exact match,
        or None if not found. Uses V1 search internally.

        Args:
            domain: Domain to search for (e.g., "acme.com")
            name: Company name to search for

        Returns:
            The matching Company, or None if not found

        Raises:
            ValueError: If neither domain nor name is provided

        Note:
            If multiple matches are found, returns the first one.
            For disambiguation, use search() directly.
        """
        if not domain and not name:
            raise ValueError("Must provide either domain or name")

        term = domain or name or ""
        result = self.search(term, page_size=10)

        for company in result.data:
            if domain and company.domain and company.domain.lower() == domain.lower():
                return company
            if name and company.name and company.name.lower() == name.lower():
                return company

        return None

    # =========================================================================
    # Write Operations (V1 API)
    # =========================================================================

    def create(self, data: CompanyCreate) -> Company:
        """
        Create a new company.

        Args:
            data: Company creation data

        Returns:
            Created company
        """
        payload: dict[str, Any] = {"name": data.name}
        if data.domain:
            payload["domain"] = data.domain
        if data.person_ids:
            payload["person_ids"] = [int(p) for p in data.person_ids]

        result = self._client.post("/organizations", json=payload, v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("company")

        return Company.model_validate(result)

    def update(
        self,
        company_id: CompanyId,
        data: CompanyUpdate,
    ) -> Company:
        """
        Update an existing company.

        Note: Cannot update name/domain of global companies.
        """
        payload: dict[str, Any] = {}
        if data.name is not None:
            payload["name"] = data.name
        if data.domain is not None:
            payload["domain"] = data.domain
        if data.person_ids is not None:
            payload["person_ids"] = [int(p) for p in data.person_ids]

        result = self._client.put(
            f"/organizations/{company_id}",
            json=payload,
            v1=True,
        )

        if self._client.cache:
            self._client.cache.invalidate_prefix("company")

        return Company.model_validate(result)

    def delete(self, company_id: CompanyId) -> bool:
        """
        Delete a company.

        Note: Cannot delete global companies.
        """
        result = self._client.delete(f"/organizations/{company_id}", v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("company")

        return bool(result.get("success", False))

    # =========================================================================
    # Merge Operations (V2 BETA)
    # =========================================================================

    def merge(
        self,
        primary_id: CompanyId,
        duplicate_id: CompanyId,
    ) -> str:
        """
        Merge a duplicate company into a primary company.

        Returns a task URL to check merge status.
        """
        if not self._client.enable_beta_endpoints:
            raise BetaEndpointDisabledError(
                "Company merge is a beta endpoint; set enable_beta_endpoints=True to use it."
            )
        result = self._client.post(
            "/company-merges",
            json={
                "primaryCompanyId": int(primary_id),
                "duplicateCompanyId": int(duplicate_id),
            },
        )
        return str(result.get("taskUrl", ""))

    def get_merge_status(self, task_id: str) -> MergeTask:
        """Check the status of a merge operation."""
        data = self._client.get(f"/tasks/company-merges/{task_id}")
        return MergeTask.model_validate(data)


class AsyncCompanyService:
    """
    Async version of CompanyService (read paths via V2).

    Scope: core read flows + auto-pagination (TR-009).
    """

    def __init__(self, client: AsyncHTTPClient):
        self._client = client

    async def list(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
    ) -> PaginatedResponse[Company]:
        """
        Get a page of companies.

        Args:
            field_ids: Specific field IDs to include in response
            field_types: Field types to include (e.g., ["enriched", "global"])
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
                (e.g., `F.field("domain").contains("acme")`)
            limit: Maximum number of results (API default: 100)

        Returns:
            Paginated response with companies
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

        data = await self._client.get("/companies", params=params or None)
        return PaginatedResponse[Company](
            data=[Company.model_validate(c) for c in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def all(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> AsyncIterator[Company]:
        """
        Iterate through all companies with automatic pagination.

        Args:
            field_ids: Specific field IDs to include
            field_types: Field types to include
            filter: V2 filter expression

        Yields:
            Company objects
        """

        async def fetch_page(next_url: str | None) -> PaginatedResponse[Company]:
            if next_url:
                data = await self._client.get_url(next_url)
                return PaginatedResponse[Company](
                    data=[Company.model_validate(c) for c in data.get("data", [])],
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
    ) -> AsyncIterator[Company]:
        """
        Auto-paginate all companies.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(field_ids=field_ids, field_types=field_types, filter=filter)

    async def get(
        self,
        company_id: CompanyId,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
    ) -> Company:
        """
        Get a single company by ID.

        Args:
            company_id: The company ID
            field_ids: Specific field IDs to include
            field_types: Field types to include

        Returns:
            Company object with requested field data
        """
        params: dict[str, Any] = {}
        if field_ids:
            params["fieldIds"] = [str(field_id) for field_id in field_ids]
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = await self._client.get(f"/companies/{company_id}", params=params or None)
        return Company.model_validate(data)
