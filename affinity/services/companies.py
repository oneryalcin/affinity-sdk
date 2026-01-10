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
    Person,
)
from ..models.pagination import (
    AsyncPageIterator,
    PageIterator,
    PaginatedResponse,
    PaginationInfo,
    V1PaginatedResponse,
)
from ..models.secondary import MergeTask
from ..models.types import AnyFieldId, CompanyId, FieldType, OpportunityId, PersonId

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
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[Company]:
        """
        Get a page of companies.

        Args:
            ids: Specific company IDs to fetch (batch lookup)
            field_ids: Specific field IDs to include in response
            field_types: Field types to include (e.g., ["enriched", "global"])
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
                (e.g., `F.field("domain").contains("acme")`)
            limit: Maximum number of results (API default: 100)
            cursor: Cursor to resume pagination (opaque; obtained from prior responses)

        Returns:
            Paginated response with companies
        """
        if cursor is not None:
            if any(p is not None for p in (ids, field_ids, field_types, filter, limit)):
                raise ValueError(
                    "Cannot combine 'cursor' with other parameters; cursor encodes all query "
                    "context. Start a new pagination sequence without a cursor to change "
                    "parameters."
                )
            data = self._client.get_url(cursor)
        else:
            params: dict[str, Any] = {}
            if ids:
                params["ids"] = [int(id_) for id_ in ids]
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

    def pages(
        self,
        *,
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Iterator[PaginatedResponse[Company]]:
        """
        Iterate company pages (not items), yielding `PaginatedResponse[Company]`.

        Useful for ETL scripts that need checkpoint/resume via `page.next_cursor`.

        Args:
            ids: Specific company IDs to fetch (batch lookup)
            field_ids: Specific field IDs to include in response
            field_types: Field types to include (e.g., ["enriched", "global"])
            filter: V2 filter expression string or FilterExpression
            limit: Maximum results per page
            cursor: Cursor to resume pagination

        Yields:
            PaginatedResponse[Company] for each page
        """
        other_params = (ids, field_ids, field_types, filter, limit)
        if cursor is not None and any(p is not None for p in other_params):
            raise ValueError(
                "Cannot combine 'cursor' with other parameters; cursor encodes all query context. "
                "Start a new pagination sequence without a cursor to change parameters."
            )
        requested_cursor = cursor
        page = (
            self.list(cursor=cursor)
            if cursor is not None
            else self.list(
                ids=ids, field_ids=field_ids, field_types=field_types, filter=filter, limit=limit
            )
        )
        while True:
            yield page
            if not page.has_next:
                return
            next_cursor = page.next_cursor
            if next_cursor is None or next_cursor == requested_cursor:
                return
            requested_cursor = next_cursor
            page = self.list(cursor=next_cursor)

    def all(
        self,
        *,
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[Company]:
        """
        Iterate through all companies with automatic pagination.

        Args:
            ids: Specific company IDs to fetch (batch lookup)
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
                    ids=ids,
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
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[Company]:
        """
        Auto-paginate all companies.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(ids=ids, field_ids=field_ids, field_types=field_types, filter=filter)

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

    def get_associated_person_ids(
        self,
        company_id: CompanyId,
        *,
        max_results: int | None = None,
    ) -> builtins.list[PersonId]:
        """
        Get associated person IDs for a company.

        V1-only exception: V2 does not expose company -> people associations.
        Uses GET `/organizations/{id}` and returns `person_ids` if present.
        """
        data = self._client.get(f"/organizations/{company_id}", v1=True)
        organization = data.get("organization") if isinstance(data, dict) else None
        source = organization if isinstance(organization, dict) else data
        person_ids = None
        if isinstance(source, dict):
            person_ids = source.get("person_ids") or source.get("personIds")

        if not isinstance(person_ids, list):
            return []

        ids = [PersonId(int(value)) for value in person_ids if value is not None]
        if max_results is not None and max_results >= 0:
            return ids[:max_results]
        return ids

    def get_associated_people(
        self,
        company_id: CompanyId,
        *,
        max_results: int | None = None,
    ) -> builtins.list[Person]:
        """
        Get associated people for a company.

        V1-only exception. Performs one request per person ID.
        """
        person_ids = self.get_associated_person_ids(company_id, max_results=max_results)
        people: builtins.list[Person] = []
        for person_id in person_ids:
            data = self._client.get(f"/persons/{person_id}", v1=True)
            people.append(Person.model_validate(data))
        return people

    def get_associated_opportunity_ids(
        self,
        company_id: CompanyId,
        *,
        max_results: int | None = None,
    ) -> builtins.list[OpportunityId]:
        """
        Get associated opportunity IDs for a company.

        V1-only: V2 does not expose company -> opportunity associations directly.
        Uses GET `/organizations/{id}` (V1) and returns `opportunity_ids`.

        Args:
            company_id: The company ID
            max_results: Maximum number of opportunity IDs to return

        Returns:
            List of OpportunityId values associated with this company
        """
        data = self._client.get(f"/organizations/{company_id}", v1=True)
        # Defensive: handle potential {"organization": {...}} wrapper
        organization = data.get("organization") if isinstance(data, dict) else None
        source = organization if isinstance(organization, dict) else data
        opp_ids = None
        if isinstance(source, dict):
            opp_ids = source.get("opportunity_ids") or source.get("opportunityIds")

        if not isinstance(opp_ids, list):
            return []

        ids = [OpportunityId(int(oid)) for oid in opp_ids if oid is not None]
        if max_results is not None and max_results >= 0:
            return ids[:max_results]
        return ids

    def get_list_entries(
        self,
        company_id: CompanyId,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[ListEntry]:
        """
        Get all list entries for a company across all lists.

        Returns comprehensive field data for each list entry.
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
            if limit:
                params["limit"] = limit
            data = self._client.get(
                f"/companies/{company_id}/list-entries",
                params=params or None,
            )

        return PaginatedResponse[ListEntry](
            data=[ListEntry.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def get_lists(
        self,
        company_id: CompanyId,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[ListSummary]:
        """Get all lists that contain this company."""
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
            if limit:
                params["limit"] = limit
            data = self._client.get(
                f"/companies/{company_id}/lists",
                params=params or None,
            )

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
            cache_key=(
                "company_fields:_all_"
                if field_types is None
                else f"company_fields:{','.join(field_types)}"
            ),
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

    def search_pages(
        self,
        term: str,
        *,
        with_interaction_dates: bool = False,
        with_interaction_persons: bool = False,
        with_opportunities: bool = False,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> Iterator[V1PaginatedResponse[Company]]:
        """
        Iterate V1 company-search result pages.

        Useful for scripts that need checkpoint/resume via `next_page_token`.

        Args:
            term: Search term (name or domain)
            with_interaction_dates: Include interaction date data
            with_interaction_persons: Include persons for interactions
            with_opportunities: Include associated opportunity IDs
            page_size: Results per page (max 500)
            page_token: Resume from this pagination token

        Yields:
            V1PaginatedResponse[Company] for each page
        """
        requested_token = page_token
        page = self.search(
            term,
            with_interaction_dates=with_interaction_dates,
            with_interaction_persons=with_interaction_persons,
            with_opportunities=with_opportunities,
            page_size=page_size,
            page_token=page_token,
        )
        while True:
            yield page
            next_token = page.next_page_token
            if not next_token or next_token == requested_token:
                return
            requested_token = next_token
            page = self.search(
                term,
                with_interaction_dates=with_interaction_dates,
                with_interaction_persons=with_interaction_persons,
                with_opportunities=with_opportunities,
                page_size=page_size,
                page_token=next_token,
            )

    def search_all(
        self,
        term: str,
        *,
        with_interaction_dates: bool = False,
        with_interaction_persons: bool = False,
        with_opportunities: bool = False,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> Iterator[Company]:
        """
        Iterate all V1 company-search results with automatic pagination.

        Args:
            term: Search term (name or domain)
            with_interaction_dates: Include interaction date data
            with_interaction_persons: Include persons for interactions
            with_opportunities: Include associated opportunity IDs
            page_size: Results per page (max 500)
            page_token: Resume from this pagination token

        Yields:
            Company objects matching the search term
        """
        for page in self.search_pages(
            term,
            with_interaction_dates=with_interaction_dates,
            with_interaction_persons=with_interaction_persons,
            with_opportunities=with_opportunities,
            page_size=page_size,
            page_token=page_token,
        ):
            yield from page.data

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
        payload = data.model_dump(by_alias=True, mode="json", exclude_none=True)
        if not data.person_ids:
            payload.pop("person_ids", None)

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
        payload = data.model_dump(
            by_alias=True,
            mode="json",
            exclude_unset=True,
            exclude_none=True,
        )

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
    Async version of CompanyService.

    Mirrors sync behavior for V2 reads, V1 writes, and V1 search helpers.
    """

    def __init__(self, client: AsyncHTTPClient):
        self._client = client

    async def list(
        self,
        *,
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[Company]:
        """
        Get a page of companies.

        Args:
            ids: Specific company IDs to fetch (batch lookup)
            field_ids: Specific field IDs to include in response
            field_types: Field types to include (e.g., ["enriched", "global"])
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
                (e.g., `F.field("domain").contains("acme")`)
            limit: Maximum number of results (API default: 100)
            cursor: Cursor to resume pagination (opaque; obtained from prior responses)

        Returns:
            Paginated response with companies
        """
        if cursor is not None:
            if any(p is not None for p in (ids, field_ids, field_types, filter, limit)):
                raise ValueError(
                    "Cannot combine 'cursor' with other parameters; cursor encodes all query "
                    "context. Start a new pagination sequence without a cursor to change "
                    "parameters."
                )
            data = await self._client.get_url(cursor)
        else:
            params: dict[str, Any] = {}
            if ids:
                params["ids"] = [int(id_) for id_ in ids]
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

    async def pages(
        self,
        *,
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncIterator[PaginatedResponse[Company]]:
        """
        Iterate company pages (not items), yielding `PaginatedResponse[Company]`.

        Useful for ETL scripts that need checkpoint/resume via `page.next_cursor`.

        Args:
            ids: Specific company IDs to fetch (batch lookup)
            field_ids: Specific field IDs to include in response
            field_types: Field types to include (e.g., ["enriched", "global"])
            filter: V2 filter expression string or FilterExpression
            limit: Maximum results per page
            cursor: Cursor to resume pagination

        Yields:
            PaginatedResponse[Company] for each page
        """
        other_params = (ids, field_ids, field_types, filter, limit)
        if cursor is not None and any(p is not None for p in other_params):
            raise ValueError(
                "Cannot combine 'cursor' with other parameters; cursor encodes all query context. "
                "Start a new pagination sequence without a cursor to change parameters."
            )
        requested_cursor = cursor
        if cursor is not None:
            page = await self.list(cursor=cursor)
        else:
            page = await self.list(
                ids=ids,
                field_ids=field_ids,
                field_types=field_types,
                filter=filter,
                limit=limit,
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

    def all(
        self,
        *,
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> AsyncIterator[Company]:
        """
        Iterate through all companies with automatic pagination.

        Args:
            ids: Specific company IDs to fetch (batch lookup)
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
            return await self.list(
                ids=ids, field_ids=field_ids, field_types=field_types, filter=filter
            )

        return AsyncPageIterator(fetch_page)

    def iter(
        self,
        *,
        ids: Sequence[CompanyId] | None = None,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> AsyncIterator[Company]:
        """
        Auto-paginate all companies.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(ids=ids, field_ids=field_ids, field_types=field_types, filter=filter)

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

    async def get_list_entries(
        self,
        company_id: CompanyId,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[ListEntry]:
        """
        Get all list entries for a company across all lists.

        Returns comprehensive field data for each list entry.
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
            if limit:
                params["limit"] = limit
            data = await self._client.get(
                f"/companies/{company_id}/list-entries",
                params=params or None,
            )

        return PaginatedResponse[ListEntry](
            data=[ListEntry.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    async def get_lists(
        self,
        company_id: CompanyId,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[ListSummary]:
        """Get all lists that contain this company."""
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
            if limit:
                params["limit"] = limit
            data = await self._client.get(
                f"/companies/{company_id}/lists",
                params=params or None,
            )

        return PaginatedResponse[ListSummary](
            data=[ListSummary.model_validate(item) for item in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    async def get_fields(
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

        data = await self._client.get(
            "/companies/fields",
            params=params or None,
            cache_key=(
                "company_fields:_all_"
                if field_types is None
                else f"company_fields:{','.join(field_types)}"
            ),
            cache_ttl=300,
        )

        return [FieldMetadata.model_validate(f) for f in data.get("data", [])]

    # =========================================================================
    # Search (V1 API)
    # =========================================================================

    async def search(
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

        data = await self._client.get("/organizations", params=params, v1=True)
        items = [Company.model_validate(o) for o in data.get("organizations", [])]
        return V1PaginatedResponse[Company](
            data=items,
            next_page_token=data.get("next_page_token"),
        )

    async def search_pages(
        self,
        term: str,
        *,
        with_interaction_dates: bool = False,
        with_interaction_persons: bool = False,
        with_opportunities: bool = False,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[V1PaginatedResponse[Company]]:
        """
        Iterate V1 company-search result pages.

        Useful for scripts that need checkpoint/resume via `next_page_token`.

        Args:
            term: Search term (name or domain)
            with_interaction_dates: Include interaction date data
            with_interaction_persons: Include persons for interactions
            with_opportunities: Include associated opportunity IDs
            page_size: Results per page (max 500)
            page_token: Resume from this pagination token

        Yields:
            V1PaginatedResponse[Company] for each page
        """
        requested_token = page_token
        page = await self.search(
            term,
            with_interaction_dates=with_interaction_dates,
            with_interaction_persons=with_interaction_persons,
            with_opportunities=with_opportunities,
            page_size=page_size,
            page_token=page_token,
        )
        while True:
            yield page
            next_token = page.next_page_token
            if not next_token or next_token == requested_token:
                return
            requested_token = next_token
            page = await self.search(
                term,
                with_interaction_dates=with_interaction_dates,
                with_interaction_persons=with_interaction_persons,
                with_opportunities=with_opportunities,
                page_size=page_size,
                page_token=next_token,
            )

    async def search_all(
        self,
        term: str,
        *,
        with_interaction_dates: bool = False,
        with_interaction_persons: bool = False,
        with_opportunities: bool = False,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[Company]:
        """
        Iterate all V1 company-search results with automatic pagination.

        Args:
            term: Search term (name or domain)
            with_interaction_dates: Include interaction date data
            with_interaction_persons: Include persons for interactions
            with_opportunities: Include associated opportunity IDs
            page_size: Results per page (max 500)
            page_token: Resume from this pagination token

        Yields:
            Company objects matching the search term
        """
        async for page in self.search_pages(
            term,
            with_interaction_dates=with_interaction_dates,
            with_interaction_persons=with_interaction_persons,
            with_opportunities=with_opportunities,
            page_size=page_size,
            page_token=page_token,
        ):
            for company in page.data:
                yield company

    async def resolve(
        self,
        *,
        domain: str | None = None,
        name: str | None = None,
    ) -> Company | None:
        """
        Find a single company by domain or name.

        This is a convenience helper that searches and returns the first exact match,
        or None if not found. Uses V1 search internally.
        """
        if not domain and not name:
            raise ValueError("Must provide either domain or name")

        term = domain or name or ""
        result = await self.search(term, page_size=10)

        for company in result.data:
            if domain and company.domain and company.domain.lower() == domain.lower():
                return company
            if name and company.name and company.name.lower() == name.lower():
                return company

        return None

    async def get_associated_person_ids(
        self,
        company_id: CompanyId,
        *,
        max_results: int | None = None,
    ) -> builtins.list[PersonId]:
        """
        Get associated person IDs for a company.

        V1-only exception: V2 does not expose company -> people associations.
        Uses GET `/organizations/{id}` and returns `person_ids` if present.
        """
        data = await self._client.get(f"/organizations/{company_id}", v1=True)
        organization = data.get("organization") if isinstance(data, dict) else None
        source = organization if isinstance(organization, dict) else data
        person_ids = None
        if isinstance(source, dict):
            person_ids = source.get("person_ids") or source.get("personIds")

        if not isinstance(person_ids, list):
            return []

        ids = [PersonId(int(value)) for value in person_ids if value is not None]
        if max_results is not None and max_results >= 0:
            return ids[:max_results]
        return ids

    async def get_associated_people(
        self,
        company_id: CompanyId,
        *,
        max_results: int | None = None,
    ) -> builtins.list[Person]:
        """
        Get associated people for a company.

        V1-only exception. Performs one request per person ID.
        """
        person_ids = await self.get_associated_person_ids(
            company_id,
            max_results=max_results,
        )
        people: builtins.list[Person] = []
        for person_id in person_ids:
            data = await self._client.get(f"/persons/{person_id}", v1=True)
            people.append(Person.model_validate(data))
        return people

    async def get_associated_opportunity_ids(
        self,
        company_id: CompanyId,
        *,
        max_results: int | None = None,
    ) -> builtins.list[OpportunityId]:
        """
        Get associated opportunity IDs for a company.

        V1-only: V2 does not expose company -> opportunity associations directly.
        Uses GET `/organizations/{id}` (V1) and returns `opportunity_ids`.

        Args:
            company_id: The company ID
            max_results: Maximum number of opportunity IDs to return

        Returns:
            List of OpportunityId values associated with this company
        """
        data = await self._client.get(f"/organizations/{company_id}", v1=True)
        # Defensive: handle potential {"organization": {...}} wrapper
        organization = data.get("organization") if isinstance(data, dict) else None
        source = organization if isinstance(organization, dict) else data
        opp_ids = None
        if isinstance(source, dict):
            opp_ids = source.get("opportunity_ids") or source.get("opportunityIds")

        if not isinstance(opp_ids, list):
            return []

        ids = [OpportunityId(int(oid)) for oid in opp_ids if oid is not None]
        if max_results is not None and max_results >= 0:
            return ids[:max_results]
        return ids

    # =========================================================================
    # Write Operations (V1 API)
    # =========================================================================

    async def create(self, data: CompanyCreate) -> Company:
        """
        Create a new company.

        Uses V1 API.
        """
        payload = data.model_dump(by_alias=True, mode="json", exclude_none=True)
        if not data.person_ids:
            payload.pop("person_ids", None)
        result = await self._client.post("/organizations", json=payload, v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("company")

        return Company.model_validate(result)

    async def update(self, company_id: CompanyId, data: CompanyUpdate) -> Company:
        """
        Update an existing company.

        Uses V1 API.
        """
        payload = data.model_dump(
            by_alias=True,
            mode="json",
            exclude_unset=True,
            exclude_none=True,
        )
        result = await self._client.put(
            f"/organizations/{company_id}",
            json=payload,
            v1=True,
        )

        if self._client.cache:
            self._client.cache.invalidate_prefix("company")

        return Company.model_validate(result)

    async def delete(self, company_id: CompanyId) -> bool:
        """
        Delete a company.

        Uses V1 API.
        """
        result = await self._client.delete(f"/organizations/{company_id}", v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("company")

        return bool(result.get("success", False))

    # =========================================================================
    # Merge Operations (V2 BETA)
    # =========================================================================

    async def merge(
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
        result = await self._client.post(
            "/company-merges",
            json={
                "primaryCompanyId": int(primary_id),
                "duplicateCompanyId": int(duplicate_id),
            },
        )
        return str(result.get("taskUrl", ""))

    async def get_merge_status(self, task_id: str) -> MergeTask:
        """Check the status of a merge operation."""
        data = await self._client.get(f"/tasks/company-merges/{task_id}")
        return MergeTask.model_validate(data)
