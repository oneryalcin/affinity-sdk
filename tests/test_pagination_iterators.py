from __future__ import annotations

import pytest

from affinity import TooManyResultsError
from affinity.models import AsyncPageIterator, PageIterator, PaginatedResponse, PaginationProgress


def _page(data: list[int], next_cursor: str | None) -> PaginatedResponse[int]:
    return PaginatedResponse[int].model_validate(
        {"data": data, "pagination": {"nextUrl": next_cursor}}
    )


def test_page_iterator_skips_empty_pages_when_next_cursor_present() -> None:
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        if url is None:
            return _page([], "u2")
        if url == "u2":
            return _page([1, 2], None)
        raise AssertionError(f"unexpected url: {url}")

    it = PageIterator(fetch_page)
    assert list(it) == [1, 2]
    assert calls == [None, "u2"]


def test_page_iterator_stops_on_empty_page_when_no_next_cursor() -> None:
    def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        return _page([], None)

    assert list(PageIterator(fetch_page)) == []


def test_page_iterator_stops_if_next_cursor_does_not_advance() -> None:
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([], "u1")

    it = PageIterator(fetch_page, initial_cursor="u1")
    assert list(it) == []
    assert calls == ["u1"]


def test_page_iterator_yields_current_page_even_if_next_cursor_loops() -> None:
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([1], "u1")

    it = PageIterator(fetch_page, initial_cursor="u1")
    assert list(it) == [1]
    assert calls == ["u1"]


@pytest.mark.asyncio
async def test_async_page_iterator_skips_empty_pages_when_next_cursor_present() -> None:
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        if url is None:
            return _page([], "u2")
        if url == "u2":
            return _page([1, 2], None)
        raise AssertionError(f"unexpected url: {url}")

    it = AsyncPageIterator(fetch_page)
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == [1, 2]
    assert calls == [None, "u2"]


@pytest.mark.asyncio
async def test_async_page_iterator_stops_on_empty_page_when_no_next_cursor() -> None:
    async def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        return _page([], None)

    it = AsyncPageIterator(fetch_page)
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == []


@pytest.mark.asyncio
async def test_async_page_iterator_stops_if_next_cursor_does_not_advance() -> None:
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([], "u1")

    it = AsyncPageIterator(fetch_page, initial_cursor="u1")
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == []
    assert calls == ["u1"]


@pytest.mark.asyncio
async def test_async_page_iterator_yields_current_page_even_if_next_cursor_loops() -> None:
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([1], "u1")

    it = AsyncPageIterator(fetch_page, initial_cursor="u1")
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == [1]
    assert calls == ["u1"]


# =============================================================================
# Edge case tests for malformed/unusual nextUrl values
# =============================================================================


def test_page_iterator_follows_empty_string_nexturl_then_stops_on_loop() -> None:
    """Empty string nextUrl is followed; loop detection stops iteration.

    The iterator treats any non-None string as a valid cursor. Empty strings
    are followed, but loop detection kicks in when the cursor doesn't change.
    """
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        if url is None:
            return _page([1, 2], "")  # First page returns empty string cursor
        # Second call with empty string - return same cursor triggers loop detection
        return _page([3], "")

    it = PageIterator(fetch_page)
    result = list(it)
    # Iterator follows empty string, gets [3], then loop detection stops
    assert result == [1, 2, 3]
    assert calls == [None, ""]


def test_page_iterator_empty_string_to_none_terminates() -> None:
    """Empty string cursor that returns None terminates normally."""
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        if url is None:
            return _page([1], "")
        if url == "":
            return _page([2], None)  # Terminate
        raise AssertionError(f"unexpected url: {url}")

    it = PageIterator(fetch_page)
    assert list(it) == [1, 2]
    assert calls == [None, ""]


def test_page_iterator_handles_unusual_cursor_strings() -> None:
    """Non-URL cursor strings are valid and followed."""
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        if url is None:
            return _page([1], "not-a-url-but-valid-cursor")
        if url == "not-a-url-but-valid-cursor":
            return _page([2], "🎉emoji-cursor🎉")
        if url == "🎉emoji-cursor🎉":
            return _page([3], None)
        raise AssertionError(f"unexpected url: {url}")

    it = PageIterator(fetch_page)
    assert list(it) == [1, 2, 3]
    assert calls == [None, "not-a-url-but-valid-cursor", "🎉emoji-cursor🎉"]


@pytest.mark.asyncio
async def test_async_page_iterator_follows_empty_string_nexturl() -> None:
    """Async iterator follows empty string cursor (async version)."""
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        if url is None:
            return _page([1], "")
        if url == "":
            return _page([2], None)
        raise AssertionError(f"unexpected url: {url}")

    it = AsyncPageIterator(fetch_page)
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == [1, 2]
    assert calls == [None, ""]


# =============================================================================
# Stress tests for many pages
# =============================================================================


def test_page_iterator_handles_many_pages() -> None:
    """Verify pagination works correctly across 100+ pages."""
    num_pages = 150
    items_per_page = 10
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        page_num = 0 if url is None else int(url.split("-")[1])
        start = page_num * items_per_page
        data = list(range(start, start + items_per_page))
        next_url = f"page-{page_num + 1}" if page_num < num_pages - 1 else None
        return _page(data, next_url)

    it = PageIterator(fetch_page)
    result = list(it)

    # Verify we got all items
    expected_total = num_pages * items_per_page
    assert len(result) == expected_total
    assert result == list(range(expected_total))

    # Verify we made the expected number of calls
    assert len(calls) == num_pages


@pytest.mark.asyncio
async def test_async_page_iterator_handles_many_pages() -> None:
    """Verify async pagination works correctly across 100+ pages."""
    num_pages = 150
    items_per_page = 10
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        page_num = 0 if url is None else int(url.split("-")[1])
        start = page_num * items_per_page
        data = list(range(start, start + items_per_page))
        next_url = f"page-{page_num + 1}" if page_num < num_pages - 1 else None
        return _page(data, next_url)

    it = AsyncPageIterator(fetch_page)
    result: list[int] = []
    async for item in it:
        result.append(item)

    # Verify we got all items
    expected_total = num_pages * items_per_page
    assert len(result) == expected_total
    assert result == list(range(expected_total))

    # Verify we made the expected number of calls
    assert len(calls) == num_pages


@pytest.mark.slow
def test_page_iterator_stress_test_large_dataset() -> None:
    """Stress test: 500 pages with varying page sizes."""
    num_pages = 500
    calls: list[str | None] = []
    total_items = 0

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        nonlocal total_items
        calls.append(url)
        page_num = 0 if url is None else int(url.split("-")[1])
        # Varying page sizes (1-20 items per page)
        page_size = (page_num % 20) + 1
        start = total_items
        data = list(range(start, start + page_size))
        total_items += page_size
        next_url = f"page-{page_num + 1}" if page_num < num_pages - 1 else None
        return _page(data, next_url)

    it = PageIterator(fetch_page)
    result = list(it)

    # Verify we made the expected number of calls
    assert len(calls) == num_pages

    # Verify items are sequential
    assert result == list(range(len(result)))


# =============================================================================
# Tests for PaginationProgress callback (Enhancement 4)
# =============================================================================


@pytest.mark.req("DX-004")
def test_page_iterator_pages_calls_on_progress() -> None:
    """Verify on_progress callback is called with correct PaginationProgress."""
    progress_calls: list[PaginationProgress] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        if url is None:
            return _page([1, 2, 3], "p2")
        if url == "p2":
            return _page([4, 5], "p3")
        if url == "p3":
            return _page([6], None)
        raise AssertionError(f"unexpected url: {url}")

    it = PageIterator(fetch_page)
    pages = list(it.pages(on_progress=progress_calls.append))

    assert len(progress_calls) == 3
    assert len(pages) == 3

    # First page
    assert progress_calls[0].page_number == 1
    assert progress_calls[0].items_in_page == 3
    assert progress_calls[0].items_so_far == 3
    assert progress_calls[0].has_next is True

    # Second page
    assert progress_calls[1].page_number == 2
    assert progress_calls[1].items_in_page == 2
    assert progress_calls[1].items_so_far == 5
    assert progress_calls[1].has_next is True

    # Third page
    assert progress_calls[2].page_number == 3
    assert progress_calls[2].items_in_page == 1
    assert progress_calls[2].items_so_far == 6
    assert progress_calls[2].has_next is False


@pytest.mark.req("DX-004")
def test_page_iterator_pages_no_callback() -> None:
    """Verify pages() works without callback."""

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        if url is None:
            return _page([1, 2], None)
        raise AssertionError(f"unexpected url: {url}")

    it = PageIterator(fetch_page)
    pages = list(it.pages())
    assert len(pages) == 1
    assert pages[0].data == [1, 2]


@pytest.mark.asyncio
@pytest.mark.req("DX-004")
async def test_async_page_iterator_pages_calls_on_progress() -> None:
    """Verify async on_progress callback is called correctly."""
    progress_calls: list[PaginationProgress] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        if url is None:
            return _page([1, 2], "p2")
        if url == "p2":
            return _page([3, 4, 5], None)
        raise AssertionError(f"unexpected url: {url}")

    it = AsyncPageIterator(fetch_page)
    pages: list[PaginatedResponse[int]] = []
    async for page in it.pages(on_progress=progress_calls.append):
        pages.append(page)

    assert len(progress_calls) == 2
    assert progress_calls[0].page_number == 1
    assert progress_calls[0].items_so_far == 2
    assert progress_calls[1].page_number == 2
    assert progress_calls[1].items_so_far == 5


# =============================================================================
# Tests for TooManyResultsError and .all() limit (Enhancement 7)
# =============================================================================


@pytest.mark.req("DX-007")
def test_page_iterator_all_returns_list() -> None:
    """Verify .all() returns a list of all items."""

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        if url is None:
            return _page([1, 2], "p2")
        if url == "p2":
            return _page([3, 4], None)
        raise AssertionError(f"unexpected url: {url}")

    it = PageIterator(fetch_page)
    result = it.all()
    assert result == [1, 2, 3, 4]
    assert isinstance(result, list)


@pytest.mark.req("DX-007")
def test_page_iterator_all_raises_too_many_results_error() -> None:
    """Verify .all() raises TooManyResultsError when limit exceeded."""
    page_num = 0

    def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        nonlocal page_num
        page_num += 1
        # Return pages with 100 items each
        start = (page_num - 1) * 100
        data = list(range(start, start + 100))
        next_url = f"p{page_num + 1}" if page_num < 20 else None
        return _page(data, next_url)

    it = PageIterator(fetch_page)
    with pytest.raises(TooManyResultsError, match="Exceeded limit=500 items"):
        it.all(limit=500)


@pytest.mark.req("DX-007")
def test_page_iterator_all_respects_custom_limit() -> None:
    """Verify .all() respects custom limit."""

    def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        return _page([1, 2, 3], None)

    it = PageIterator(fetch_page)
    result = it.all(limit=10)
    assert result == [1, 2, 3]


@pytest.mark.req("DX-007")
def test_page_iterator_all_unlimited() -> None:
    """Verify .all(limit=None) disables the limit check."""
    page_num = 0

    def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        nonlocal page_num
        page_num += 1
        if page_num <= 3:
            return _page([page_num], f"p{page_num + 1}")
        return _page([page_num], None)

    it = PageIterator(fetch_page)
    result = it.all(limit=None)
    assert result == [1, 2, 3, 4]


@pytest.mark.asyncio
@pytest.mark.req("DX-007")
async def test_async_page_iterator_all_returns_list() -> None:
    """Verify async .all() returns a list."""

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        if url is None:
            return _page([1, 2], "p2")
        if url == "p2":
            return _page([3], None)
        raise AssertionError(f"unexpected url: {url}")

    it = AsyncPageIterator(fetch_page)
    result = await it.all()
    assert result == [1, 2, 3]


@pytest.mark.asyncio
@pytest.mark.req("DX-007")
async def test_async_page_iterator_all_raises_too_many_results_error() -> None:
    """Verify async .all() raises TooManyResultsError when limit exceeded."""
    page_num = 0

    async def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        nonlocal page_num
        page_num += 1
        start = (page_num - 1) * 100
        data = list(range(start, start + 100))
        next_url = f"p{page_num + 1}" if page_num < 20 else None
        return _page(data, next_url)

    it = AsyncPageIterator(fetch_page)
    with pytest.raises(TooManyResultsError, match="Exceeded limit=500 items"):
        await it.all(limit=500)
