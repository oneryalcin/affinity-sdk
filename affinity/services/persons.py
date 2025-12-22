"""
Person service.

Provides operations for managing persons (contacts) in Affinity.
Uses V2 API for reading, V1 API for writing.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from ..exceptions import BetaEndpointDisabledError
from ..filters import FilterExpression
from ..models.entities import (
    FieldMetadata,
    ListEntry,
    ListSummary,
    Person,
    PersonCreate,
    PersonUpdate,
)
from ..models.pagination import (
    AsyncPageIterator,
    PageIterator,
    PaginatedResponse,
    PaginationInfo,
    V1PaginatedResponse,
)
from ..models.secondary import MergeTask
from ..models.types import AnyFieldId, FieldType, PersonId

if TYPE_CHECKING:
    from ..clients.http import AsyncHTTPClient, HTTPClient


class PersonService:
    """
    Service for managing persons (contacts).

    Uses V2 API for efficient reading with field selection,
    V1 API for create/update/delete operations.
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
        cursor: str | None = None,
    ) -> PaginatedResponse[Person]:
        """
        Get a page of persons.

        Args:
            field_ids: Specific field IDs to include in response
            field_types: Field types to include
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
            limit: Maximum number of results
            cursor: Cursor to resume pagination (opaque; obtained from prior responses)

        Returns:
            Paginated response with persons
        """
        if cursor is not None:
            if any(p is not None for p in (field_ids, field_types, filter, limit)):
                raise ValueError(
                    "Cannot combine 'cursor' with other parameters; cursor encodes all query "
                    "context. Start a new pagination sequence without a cursor to change "
                    "parameters."
                )
            data = self._client.get_url(cursor)
        else:
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
            data = self._client.get("/persons", params=params or None)

        return PaginatedResponse[Person](
            data=[Person.model_validate(p) for p in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def pages(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Iterator[PaginatedResponse[Person]]:
        """
        Iterate person pages (not items), yielding `PaginatedResponse[Person]`.

        This is useful for ETL scripts that want checkpoint/resume via `page.next_cursor`.
        """
        other_params = (field_ids, field_types, filter, limit)
        if cursor is not None and any(p is not None for p in other_params):
            raise ValueError(
                "Cannot combine 'cursor' with other parameters; cursor encodes all query context. "
                "Start a new pagination sequence without a cursor to change parameters."
            )
        requested_cursor = cursor
        page = (
            self.list(cursor=cursor)
            if cursor is not None
            else self.list(field_ids=field_ids, field_types=field_types, filter=filter, limit=limit)
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
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> Iterator[Person]:
        """
        Iterate through all persons with automatic pagination.

        Yields:
            Person objects
        """

        def fetch_page(next_url: str | None) -> PaginatedResponse[Person]:
            if next_url:
                data = self._client.get_url(next_url)
                return PaginatedResponse[Person](
                    data=[Person.model_validate(p) for p in data.get("data", [])],
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
    ) -> Iterator[Person]:
        """
        Auto-paginate all persons.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(field_ids=field_ids, field_types=field_types, filter=filter)

    def get(
        self,
        person_id: PersonId,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
    ) -> Person:
        """
        Get a single person by ID.

        Args:
            person_id: The person ID
            field_ids: Specific field IDs to include
            field_types: Field types to include

        Returns:
            Person object with requested field data
        """
        params: dict[str, Any] = {}
        if field_ids:
            params["fieldIds"] = [str(field_id) for field_id in field_ids]
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = self._client.get(
            f"/persons/{person_id}",
            params=params or None,
        )
        return Person.model_validate(data)

    def get_list_entries(
        self,
        person_id: PersonId,
    ) -> PaginatedResponse[ListEntry]:
        """Get all list entries for a person across all lists."""
        data = self._client.get(f"/persons/{person_id}/list-entries")

        return PaginatedResponse[ListEntry](
            data=[ListEntry.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    def get_lists(
        self,
        person_id: PersonId,
    ) -> PaginatedResponse[ListSummary]:
        """Get all lists that contain this person."""
        data = self._client.get(f"/persons/{person_id}/lists")

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
        Get metadata about person fields.

        Cached for performance.
        """
        params: dict[str, Any] = {}
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = self._client.get(
            "/persons/fields",
            params=params or None,
            cache_key=f"person_fields:{','.join(field_types or [])}",
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
    ) -> V1PaginatedResponse[Person]:
        """
        Search for persons by name or email.

        Uses V1 API for search functionality.

        Args:
            term: Search term (name or email)
            with_interaction_dates: Include interaction date data
            with_interaction_persons: Include persons for interactions
            with_opportunities: Include associated opportunity IDs
            page_size: Results per page (max 500)
            page_token: Pagination token

        Returns:
            Dict with 'persons' and 'next_page_token'
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

        data = self._client.get("/persons", params=params, v1=True)
        items = [Person.model_validate(p) for p in data.get("persons", [])]
        return V1PaginatedResponse[Person](
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
    ) -> Iterator[V1PaginatedResponse[Person]]:
        """
        Iterate V1 person-search result pages.

        This is useful for scripts that want to checkpoint/resume with a
        `next_page_token`.
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
    ) -> Iterator[Person]:
        """Iterate all V1 person-search results with automatic pagination."""
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
        email: str | None = None,
        name: str | None = None,
    ) -> Person | None:
        """
        Find a single person by email or name.

        This is a convenience helper that searches and returns the first exact match,
        or None if not found. Uses V1 search internally.

        Args:
            email: Email address to search for
            name: Person name to search for (first + last)

        Returns:
            The matching Person, or None if not found

        Raises:
            ValueError: If neither email nor name is provided

        Note:
            If multiple matches are found, returns the first one.
            For disambiguation, use search() directly.
        """
        if not email and not name:
            raise ValueError("Must provide either email or name")

        term = email or name or ""
        result = self.search(term, page_size=10)

        for person in result.data:
            if email:
                # Check primary email and all emails
                if person.primary_email and person.primary_email.lower() == email.lower():
                    return person
                if person.emails:
                    for e in person.emails:
                        if e.lower() == email.lower():
                            return person
            if name:
                # Check full name
                full_name = f"{person.first_name or ''} {person.last_name or ''}".strip()
                if full_name.lower() == name.lower():
                    return person

        return None

    # =========================================================================
    # Write Operations (V1 API)
    # =========================================================================

    def create(self, data: PersonCreate) -> Person:
        """
        Create a new person.

        Raises:
            ValidationError: If email conflicts with existing person
        """
        payload: dict[str, Any] = {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "emails": data.emails,
        }
        if data.company_ids:
            payload["organization_ids"] = [int(o) for o in data.company_ids]

        result = self._client.post("/persons", json=payload, v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("person")

        return Person.model_validate(result)

    def update(
        self,
        person_id: PersonId,
        data: PersonUpdate,
    ) -> Person:
        """
        Update an existing person.

        Note: To add emails/organizations, include existing values plus new ones.
        """
        payload: dict[str, Any] = {}
        if data.first_name is not None:
            payload["first_name"] = data.first_name
        if data.last_name is not None:
            payload["last_name"] = data.last_name
        if data.emails is not None:
            payload["emails"] = data.emails
        if data.company_ids is not None:
            payload["organization_ids"] = [int(o) for o in data.company_ids]

        result = self._client.put(
            f"/persons/{person_id}",
            json=payload,
            v1=True,
        )

        if self._client.cache:
            self._client.cache.invalidate_prefix("person")

        return Person.model_validate(result)

    def delete(self, person_id: PersonId) -> bool:
        """Delete a person (also deletes associated field values)."""
        result = self._client.delete(f"/persons/{person_id}", v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("person")

        return bool(result.get("success", False))

    # =========================================================================
    # Merge Operations (V2 BETA)
    # =========================================================================

    def merge(
        self,
        primary_id: PersonId,
        duplicate_id: PersonId,
    ) -> str:
        """
        Merge a duplicate person into a primary person.

        Returns a task URL to check merge status.
        """
        if not self._client.enable_beta_endpoints:
            raise BetaEndpointDisabledError(
                "Person merge is a beta endpoint; set enable_beta_endpoints=True to use it."
            )
        result = self._client.post(
            "/person-merges",
            json={
                "primaryPersonId": int(primary_id),
                "duplicatePersonId": int(duplicate_id),
            },
        )
        return str(result.get("taskUrl", ""))

    def get_merge_status(self, task_id: str) -> MergeTask:
        """Check the status of a merge operation."""
        data = self._client.get(f"/tasks/person-merges/{task_id}")
        return MergeTask.model_validate(data)


class AsyncPersonService:
    """Async version of PersonService."""

    def __init__(self, client: AsyncHTTPClient):
        self._client = client

    async def list(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedResponse[Person]:
        """
        Get a page of persons.

        Args:
            field_ids: Specific field IDs to include in response
            field_types: Field types to include
            filter: V2 filter expression string, or a FilterExpression built via `affinity.F`
            limit: Maximum number of results
            cursor: Cursor to resume pagination (opaque; obtained from prior responses)

        Returns:
            Paginated response with persons
        """
        if cursor is not None:
            if any(p is not None for p in (field_ids, field_types, filter, limit)):
                raise ValueError(
                    "Cannot combine 'cursor' with other parameters; cursor encodes all query "
                    "context. Start a new pagination sequence without a cursor to change "
                    "parameters."
                )
            data = await self._client.get_url(cursor)
        else:
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
            data = await self._client.get("/persons", params=params or None)

        return PaginatedResponse[Person](
            data=[Person.model_validate(p) for p in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    async def pages(
        self,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncIterator[PaginatedResponse[Person]]:
        """
        Iterate person pages (not items), yielding `PaginatedResponse[Person]`.

        This is useful for ETL scripts that want checkpoint/resume via `page.next_cursor`.
        """
        other_params = (field_ids, field_types, filter, limit)
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
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
        filter: str | FilterExpression | None = None,
    ) -> AsyncIterator[Person]:
        """
        Iterate through all persons with automatic pagination.

        Yields:
            Person objects
        """

        async def fetch_page(next_url: str | None) -> PaginatedResponse[Person]:
            if next_url:
                data = await self._client.get_url(next_url)
                return PaginatedResponse[Person](
                    data=[Person.model_validate(p) for p in data.get("data", [])],
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
    ) -> AsyncIterator[Person]:
        """
        Auto-paginate all persons.

        Alias for `all()` (FR-006 public contract).
        """
        return self.all(field_ids=field_ids, field_types=field_types, filter=filter)

    async def get(
        self,
        person_id: PersonId,
        *,
        field_ids: Sequence[AnyFieldId] | None = None,
        field_types: Sequence[FieldType] | None = None,
    ) -> Person:
        """
        Get a single person by ID.

        Args:
            person_id: The person ID
            field_ids: Specific field IDs to include
            field_types: Field types to include

        Returns:
            Person object with requested field data
        """
        params: dict[str, Any] = {}
        if field_ids:
            params["fieldIds"] = [str(field_id) for field_id in field_ids]
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = await self._client.get(f"/persons/{person_id}", params=params or None)
        return Person.model_validate(data)

    async def get_list_entries(
        self,
        person_id: PersonId,
    ) -> PaginatedResponse[ListEntry]:
        """Get all list entries for a person across all lists."""
        data = await self._client.get(f"/persons/{person_id}/list-entries")

        return PaginatedResponse[ListEntry](
            data=[ListEntry.model_validate(e) for e in data.get("data", [])],
            pagination=PaginationInfo.model_validate(data.get("pagination", {})),
        )

    async def get_lists(
        self,
        person_id: PersonId,
    ) -> PaginatedResponse[ListSummary]:
        """Get all lists that contain this person."""
        data = await self._client.get(f"/persons/{person_id}/lists")

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
        Get metadata about person fields.

        Cached for performance.
        """
        params: dict[str, Any] = {}
        if field_types:
            params["fieldTypes"] = [field_type.value for field_type in field_types]

        data = await self._client.get(
            "/persons/fields",
            params=params or None,
            cache_key=f"person_fields:{','.join(field_types or [])}",
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
    ) -> V1PaginatedResponse[Person]:
        """
        Search for persons by name or email.

        Uses V1 API for search functionality.
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

        data = await self._client.get("/persons", params=params, v1=True)
        items = [Person.model_validate(p) for p in data.get("persons", [])]
        return V1PaginatedResponse[Person](
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
    ) -> AsyncIterator[V1PaginatedResponse[Person]]:
        """
        Iterate V1 person-search result pages.

        This is useful for scripts that want to checkpoint/resume with a
        `next_page_token`.
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
    ) -> AsyncIterator[Person]:
        """Iterate all V1 person-search results with automatic pagination."""
        async for page in self.search_pages(
            term,
            with_interaction_dates=with_interaction_dates,
            with_interaction_persons=with_interaction_persons,
            with_opportunities=with_opportunities,
            page_size=page_size,
            page_token=page_token,
        ):
            for person in page.data:
                yield person

    async def resolve(
        self,
        *,
        email: str | None = None,
        name: str | None = None,
    ) -> Person | None:
        """
        Find a single person by email or name.

        This is a convenience helper that searches and returns the first exact match,
        or None if not found. Uses V1 search internally.
        """
        if not email and not name:
            raise ValueError("Must provide either email or name")

        term = email or name or ""
        result = await self.search(term, page_size=10)

        for person in result.data:
            if email:
                if person.primary_email and person.primary_email.lower() == email.lower():
                    return person
                if person.emails:
                    for e in person.emails:
                        if e.lower() == email.lower():
                            return person
            if name:
                full_name = f"{person.first_name or ''} {person.last_name or ''}".strip()
                if full_name.lower() == name.lower():
                    return person

        return None

    # =========================================================================
    # Write Operations (V1 API)
    # =========================================================================

    async def create(self, data: PersonCreate) -> Person:
        """
        Create a new person.

        Raises:
            ValidationError: If email conflicts with existing person
        """
        payload: dict[str, Any] = {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "emails": data.emails,
        }
        if data.company_ids:
            payload["organization_ids"] = [int(o) for o in data.company_ids]

        result = await self._client.post("/persons", json=payload, v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("person")

        return Person.model_validate(result)

    async def update(
        self,
        person_id: PersonId,
        data: PersonUpdate,
    ) -> Person:
        """
        Update an existing person.

        Note: To add emails/organizations, include existing values plus new ones.
        """
        payload: dict[str, Any] = {}
        if data.first_name is not None:
            payload["first_name"] = data.first_name
        if data.last_name is not None:
            payload["last_name"] = data.last_name
        if data.emails is not None:
            payload["emails"] = data.emails
        if data.company_ids is not None:
            payload["organization_ids"] = [int(o) for o in data.company_ids]

        result = await self._client.put(
            f"/persons/{person_id}",
            json=payload,
            v1=True,
        )

        if self._client.cache:
            self._client.cache.invalidate_prefix("person")

        return Person.model_validate(result)

    async def delete(self, person_id: PersonId) -> bool:
        """Delete a person (also deletes associated field values)."""
        result = await self._client.delete(f"/persons/{person_id}", v1=True)

        if self._client.cache:
            self._client.cache.invalidate_prefix("person")

        return bool(result.get("success", False))

    # =========================================================================
    # Merge Operations (V2 BETA)
    # =========================================================================

    async def merge(
        self,
        primary_id: PersonId,
        duplicate_id: PersonId,
    ) -> str:
        """
        Merge a duplicate person into a primary person.

        Returns a task URL to check merge status.
        """
        if not self._client.enable_beta_endpoints:
            raise BetaEndpointDisabledError(
                "Person merge is a beta endpoint; set enable_beta_endpoints=True to use it."
            )
        result = await self._client.post(
            "/person-merges",
            json={
                "primaryPersonId": int(primary_id),
                "duplicatePersonId": int(duplicate_id),
            },
        )
        return str(result.get("taskUrl", ""))

    async def get_merge_status(self, task_id: str) -> MergeTask:
        """Check the status of a merge operation."""
        data = await self._client.get(f"/tasks/person-merges/{task_id}")
        return MergeTask.model_validate(data)
