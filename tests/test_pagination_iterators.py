from __future__ import annotations

import pytest

from affinity.models import AsyncPageIterator, PageIterator, PaginatedResponse


def _page(data: list[int], next_url: str | None) -> PaginatedResponse[int]:
    return PaginatedResponse[int].model_validate(
        {"data": data, "pagination": {"nextUrl": next_url}}
    )


def test_page_iterator_skips_empty_pages_when_next_url_present() -> None:
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


def test_page_iterator_stops_on_empty_page_when_no_next_url() -> None:
    def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        return _page([], None)

    assert list(PageIterator(fetch_page)) == []


def test_page_iterator_stops_if_next_url_does_not_advance() -> None:
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([], "u1")

    it = PageIterator(fetch_page, initial_url="u1")
    assert list(it) == []
    assert calls == ["u1"]


def test_page_iterator_yields_current_page_even_if_next_url_loops() -> None:
    calls: list[str | None] = []

    def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([1], "u1")

    it = PageIterator(fetch_page, initial_url="u1")
    assert list(it) == [1]
    assert calls == ["u1"]


@pytest.mark.asyncio
async def test_async_page_iterator_skips_empty_pages_when_next_url_present() -> None:
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
async def test_async_page_iterator_stops_on_empty_page_when_no_next_url() -> None:
    async def fetch_page(_url: str | None) -> PaginatedResponse[int]:
        return _page([], None)

    it = AsyncPageIterator(fetch_page)
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == []


@pytest.mark.asyncio
async def test_async_page_iterator_stops_if_next_url_does_not_advance() -> None:
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([], "u1")

    it = AsyncPageIterator(fetch_page, initial_url="u1")
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == []
    assert calls == ["u1"]


@pytest.mark.asyncio
async def test_async_page_iterator_yields_current_page_even_if_next_url_loops() -> None:
    calls: list[str | None] = []

    async def fetch_page(url: str | None) -> PaginatedResponse[int]:
        calls.append(url)
        return _page([1], "u1")

    it = AsyncPageIterator(fetch_page, initial_url="u1")
    items: list[int] = []
    async for item in it:
        items.append(item)
    assert items == [1]
    assert calls == ["u1"]
