"""Additional tests for affinity.services.opportunities to improve coverage."""

from __future__ import annotations

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.models.types import OpportunityId
from affinity.services.opportunities import OpportunityService


class TestOpportunityServiceValidationErrors:
    """Tests for validation error branches in OpportunityService."""

    @pytest.fixture
    def service(self) -> OpportunityService:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
                request=request,
            )

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        return OpportunityService(http)

    def test_list_cursor_with_limit_raises(self, service: OpportunityService) -> None:
        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            service.list(cursor="some-cursor", limit=10)

    def test_pages_cursor_with_limit_raises(self, service: OpportunityService) -> None:
        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            list(service.pages(cursor="some-cursor", limit=10))


class TestOpportunityServicePagination:
    """Tests for opportunity pagination."""

    def test_pages_iterates_multiple_pages(self) -> None:
        page_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal page_count
            page_count += 1

            if page_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "data": [{"id": 1, "name": "Opp 1"}],
                        "pagination": {"nextUrl": "https://v2.example/v2/opportunities?cursor=p2"},
                    },
                    request=request,
                )
            elif page_count == 2:
                return httpx.Response(
                    200,
                    json={
                        "data": [{"id": 2, "name": "Opp 2"}],
                        "pagination": {"nextUrl": None},
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
                request=request,
            )

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        pages = list(service.pages())
        assert len(pages) == 2
        assert len(pages[0].data) == 1
        assert pages[0].data[0].name == "Opp 1"
        assert len(pages[1].data) == 1
        assert pages[1].data[0].name == "Opp 2"

    def test_pages_stops_on_same_cursor(self) -> None:
        """Pages should stop if cursor doesn't advance (prevents infinite loop)."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            # Always return the same next cursor - should stop after first page
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "name": "Opp"}],
                    "pagination": {"nextUrl": "https://v2.example/v2/opportunities?cursor=same"},
                },
                request=request,
            )

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        # Start with cursor="same" - should return one page then stop
        pages = list(service.pages(cursor="https://v2.example/v2/opportunities?cursor=same"))
        assert len(pages) == 1
        assert call_count == 1

    def test_all_iterates_all_opportunities(self) -> None:
        page_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal page_count
            page_count += 1

            if page_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "data": [{"id": 1, "name": "Opp 1"}, {"id": 2, "name": "Opp 2"}],
                        "pagination": {"nextUrl": "https://v2.example/v2/opportunities?cursor=p2"},
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 3, "name": "Opp 3"}],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        opps = list(service.all())
        assert len(opps) == 3
        assert [o.id for o in opps] == [1, 2, 3]


class TestOpportunityServiceGet:
    """Tests for getting individual opportunities."""

    def test_get_by_id(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/opportunities/123" in str(request.url):
                return httpx.Response(
                    200,
                    json={"id": 123, "name": "Test Opportunity"},
                    request=request,
                )
            return httpx.Response(404, json={"error": "Not found"}, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        opp = service.get(OpportunityId(123))
        assert opp.id == 123
        assert opp.name == "Test Opportunity"


class TestOpportunityServiceSearch:
    """Tests for opportunity search (V1 API)."""

    def test_search_with_term(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            # V1 API uses /opportunities endpoint
            if "v1.example/opportunities" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "opportunities": [{"id": 1, "name": "Matching Opportunity"}],
                        "next_page_token": None,
                    },
                    request=request,
                )
            return httpx.Response(404, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        result = service.search(term="test")
        assert len(result.data) == 1
        assert result.data[0].name == "Matching Opportunity"

    def test_search_with_page_size(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "v1.example/opportunities" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "opportunities": [{"id": 1, "name": "Opp"}],
                        "next_page_token": "token123",
                    },
                    request=request,
                )
            return httpx.Response(404, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        result = service.search(page_size=10)
        assert len(result.data) == 1
        assert result.next_page_token == "token123"

    def test_search_pages_iterates(self) -> None:
        page_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal page_count
            page_count += 1

            if page_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "opportunities": [{"id": 1, "name": "Opp 1"}],
                        "next_page_token": "page2",
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "opportunities": [{"id": 2, "name": "Opp 2"}],
                    "next_page_token": None,
                },
                request=request,
            )

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        pages = list(service.search_pages())
        assert len(pages) == 2
        assert pages[0].data[0].name == "Opp 1"
        assert pages[1].data[0].name == "Opp 2"

    def test_search_all_iterates(self) -> None:
        page_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal page_count
            page_count += 1

            if page_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "opportunities": [{"id": 1, "name": "Opp 1"}],
                        "next_page_token": "page2",
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "opportunities": [{"id": 2, "name": "Opp 2"}],
                    "next_page_token": None,
                },
                request=request,
            )

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = OpportunityService(http)

        opps = list(service.search_all())
        assert len(opps) == 2
        assert [o.name for o in opps] == ["Opp 1", "Opp 2"]
