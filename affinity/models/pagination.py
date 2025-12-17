"""
Pagination, response wrappers, and utility models.

Provides type-safe access to paginated API responses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AffinityModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        use_enum_values=True,
    )


# =============================================================================
# Pagination Models
# =============================================================================


class PaginationInfo(AffinityModel):
    """V2 pagination info returned in responses."""

    next_url: str | None = Field(None, alias="nextUrl")
    prev_url: str | None = Field(None, alias="prevUrl")


class PaginationInfoWithTotal(PaginationInfo):
    """Pagination with total count (used by some endpoints)."""

    total_count: int = Field(0, alias="totalCount")


# =============================================================================
# Generic Paginated Response
# =============================================================================


class PaginatedResponse(AffinityModel, Generic[T]):
    """
    A paginated response from the API.

    Provides access to the current page of results and pagination info.
    """

    data: list[T] = Field(default_factory=list)
    pagination: PaginationInfo = Field(default_factory=PaginationInfo)

    def __len__(self) -> int:
        """Number of items in current page."""
        return len(self.data)

    @property
    def has_next(self) -> bool:
        """Whether there are more pages."""
        return self.pagination.next_url is not None

    @property
    def next_url(self) -> str | None:
        """URL for the next page, if any."""
        return self.pagination.next_url


# =============================================================================
# Auto-paginating Iterator
# =============================================================================


class PageIterator(Generic[T]):
    """
    Synchronous iterator that automatically fetches all pages.

    Usage:
        for item in client.companies.all():
            print(item.name)
    """

    def __init__(
        self,
        fetch_page: Callable[[str | None], PaginatedResponse[T]],
        initial_url: str | None = None,
    ):
        self._fetch_page = fetch_page
        self._next_url = initial_url
        self._current_page: list[T] = []
        self._index = 0
        self._exhausted = False

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        while True:
            # If we have items in current page, return next
            if self._index < len(self._current_page):
                item = self._current_page[self._index]
                self._index += 1
                return item

            # Need to fetch next page
            if self._exhausted:
                raise StopIteration

            requested_url = self._next_url
            response = self._fetch_page(requested_url)
            self._current_page = list(response.data)
            self._next_url = response.next_url
            self._index = 0

            # Guard against pagination loops (no cursor progress).
            if response.has_next and response.next_url == requested_url:
                self._exhausted = True

            # Empty pages can still legitimately include nextUrl; keep paging
            # until we get data or the cursor is exhausted.
            if not self._current_page:
                if response.has_next and not self._exhausted:
                    continue
                self._exhausted = True
                raise StopIteration

            if not response.has_next:
                self._exhausted = True


class AsyncPageIterator(Generic[T]):
    """
    Asynchronous iterator that automatically fetches all pages.

    Usage:
        async for item in client.companies.all():
            print(item.name)
    """

    def __init__(
        self,
        fetch_page: Callable[[str | None], Awaitable[PaginatedResponse[T]]],
        initial_url: str | None = None,
    ):
        self._fetch_page = fetch_page
        self._next_url = initial_url
        self._current_page: list[T] = []
        self._index = 0
        self._exhausted = False

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        while True:
            # If we have items in current page, return next
            if self._index < len(self._current_page):
                item = self._current_page[self._index]
                self._index += 1
                return item

            # Need to fetch next page
            if self._exhausted:
                raise StopAsyncIteration

            requested_url = self._next_url
            response = await self._fetch_page(requested_url)
            self._current_page = list(response.data)
            self._next_url = response.next_url
            self._index = 0

            # Guard against pagination loops (no cursor progress).
            if response.has_next and response.next_url == requested_url:
                self._exhausted = True

            # Empty pages can still legitimately include nextUrl; keep paging
            # until we get data or the cursor is exhausted.
            if not self._current_page:
                if response.has_next and not self._exhausted:
                    continue
                self._exhausted = True
                raise StopAsyncIteration

            if not response.has_next:
                self._exhausted = True


# =============================================================================
# V1 Pagination Response (uses page_token)
# =============================================================================


class V1PaginatedResponse(AffinityModel, Generic[T]):
    """V1 API pagination format using page_token."""

    data: list[T] = Field(default_factory=list)
    next_page_token: str | None = Field(None, alias="nextPageToken")

    @property
    def has_next(self) -> bool:
        return self.next_page_token is not None


# =============================================================================
# Batch Operation Response (V2)
# =============================================================================


class BatchOperationResult(AffinityModel):
    """Result of a single operation in a batch."""

    field_id: str = Field(alias="fieldId")
    success: bool
    error: str | None = None


class BatchOperationResponse(AffinityModel):
    """Response from batch field operations."""

    results: list[BatchOperationResult] = Field(default_factory=list)

    @property
    def all_successful(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def failures(self) -> list[BatchOperationResult]:
        return [r for r in self.results if not r.success]


# =============================================================================
# Success Response (V1 delete operations)
# =============================================================================


class SuccessResponse(AffinityModel):
    """Simple success response from V1 delete operations."""

    success: bool
