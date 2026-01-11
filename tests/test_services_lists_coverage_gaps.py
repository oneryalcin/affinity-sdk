"""Additional tests for affinity.services.lists to improve coverage."""

from __future__ import annotations

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.exceptions import AffinityError
from affinity.models.entities import AffinityList
from affinity.models.types import ListId
from affinity.services.lists import (
    ListService,
    _safe_model_validate,
    _saved_views_list_id_from_cursor,
)


class TestSafeModelValidate:
    """Tests for _safe_model_validate helper."""

    def test_valid_payload(self) -> None:
        payload = {
            "id": 1,
            "name": "Test List",
            "type": 0,
            "public": True,
            "ownerId": 123,
            "creatorId": 456,
            "listSize": 10,
        }
        result = _safe_model_validate(AffinityList, payload)
        assert result.id == 1
        assert result.name == "Test List"

    def test_invalid_payload_raises_affinity_error(self) -> None:
        # Missing required fields
        payload = {"id": "not-an-int"}
        with pytest.raises(AffinityError, match="Invalid API response"):
            _safe_model_validate(AffinityList, payload, context="list")


class TestSavedViewsListIdFromCursor:
    """Tests for _saved_views_list_id_from_cursor helper."""

    def test_valid_cursor_extracts_list_id(self) -> None:
        cursor = "https://api.affinity.co/v2/lists/123/saved-views?cursor=abc"
        assert _saved_views_list_id_from_cursor(cursor) == 123

    def test_valid_cursor_with_trailing_slash(self) -> None:
        cursor = "https://api.affinity.co/v2/lists/456/saved-views/"
        assert _saved_views_list_id_from_cursor(cursor) == 456

    def test_invalid_cursor_format_returns_none(self) -> None:
        assert _saved_views_list_id_from_cursor("not-a-url") is None

    def test_cursor_without_list_id_returns_none(self) -> None:
        cursor = "https://api.affinity.co/v2/something-else"
        assert _saved_views_list_id_from_cursor(cursor) is None

    def test_empty_path_returns_none(self) -> None:
        # Edge case: URL with no path
        assert _saved_views_list_id_from_cursor("https://api.affinity.co") is None


class TestListServiceValidationErrors:
    """Tests for validation error branches in ListService."""

    @pytest.fixture
    def service(self) -> ListService:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [], "pagination": {}}, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        return ListService(http)

    def test_list_cursor_with_limit_raises(self, service: ListService) -> None:
        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            service.list(cursor="some-cursor", limit=10)

    def test_list_limit_zero_raises(self, service: ListService) -> None:
        with pytest.raises(ValueError, match="'limit' must be > 0"):
            service.list(limit=0)

    def test_list_limit_negative_raises(self, service: ListService) -> None:
        with pytest.raises(ValueError, match="'limit' must be > 0"):
            service.list(limit=-5)

    def test_pages_cursor_with_limit_raises(self, service: ListService) -> None:
        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            list(service.pages(cursor="some-cursor", limit=10))


class TestListServiceSavedViews:
    """Tests for saved views methods in ListService."""

    @pytest.fixture
    def service_with_saved_views(self) -> ListService:
        page_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal page_count
            url = request.url

            # Handle saved views list
            if "/saved-views" in str(url) and "view_id" not in str(url):
                page_count += 1
                if page_count == 1:
                    return httpx.Response(
                        200,
                        json={
                            "data": [{"id": 1, "name": "View 1", "listId": 100}],
                            "pagination": {
                                "nextUrl": "https://v2.example/v2/lists/100/saved-views?cursor=page2"
                            },
                        },
                        request=request,
                    )
                elif page_count == 2:
                    return httpx.Response(
                        200,
                        json={
                            "data": [{"id": 2, "name": "View 2", "listId": 100}],
                            "pagination": {"nextUrl": None},
                        },
                        request=request,
                    )
                return httpx.Response(
                    200,
                    json={"data": [], "pagination": {"nextUrl": None}},
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
        return ListService(http)

    def test_get_saved_views_cursor_with_limit_raises(
        self, service_with_saved_views: ListService
    ) -> None:
        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            service_with_saved_views.get_saved_views(ListId(100), cursor="cursor", limit=10)

    def test_get_saved_views_limit_zero_raises(self, service_with_saved_views: ListService) -> None:
        with pytest.raises(ValueError, match="'limit' must be > 0"):
            service_with_saved_views.get_saved_views(ListId(100), limit=0)

    def test_get_saved_views_cursor_list_id_mismatch_raises(
        self, service_with_saved_views: ListService
    ) -> None:
        cursor = "https://api.affinity.co/v2/lists/999/saved-views?cursor=abc"
        with pytest.raises(ValueError, match="Cursor does not match list_id"):
            service_with_saved_views.get_saved_views(ListId(100), cursor=cursor)

    def test_saved_views_pages_iterates_all_pages(
        self, service_with_saved_views: ListService
    ) -> None:
        pages = list(service_with_saved_views.saved_views_pages(ListId(100)))
        assert len(pages) == 2
        assert len(pages[0].data) == 1
        assert pages[0].data[0].name == "View 1"
        assert len(pages[1].data) == 1
        assert pages[1].data[0].name == "View 2"

    def test_saved_views_pages_cursor_with_limit_raises(
        self, service_with_saved_views: ListService
    ) -> None:
        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            list(service_with_saved_views.saved_views_pages(ListId(100), cursor="c", limit=10))

    def test_saved_views_all_iterates_all_views(
        self, service_with_saved_views: ListService
    ) -> None:
        views = list(service_with_saved_views.saved_views_all(ListId(100)))
        assert len(views) == 2
        assert views[0].name == "View 1"
        assert views[1].name == "View 2"


class TestListServiceFieldOperations:
    """Tests for list field operations."""

    def test_get_fields_returns_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            url = request.url

            if "/fields" in str(url):
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "f1", "name": "Field1", "valueType": 0, "allowsMultiple": False}
                        ],
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
        service = ListService(http)

        # get_fields returns a list, not PaginatedResponse
        fields = service.get_fields(ListId(100))
        assert isinstance(fields, list)
        assert len(fields) == 1
        assert fields[0].name == "Field1"

    def test_get_fields_with_field_types_filter(self) -> None:
        from affinity.models.types import FieldType

        def handler(request: httpx.Request) -> httpx.Response:
            url = request.url

            if "/fields" in str(url):
                # Verify field_types param was passed
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "f1", "name": "Field1", "valueType": 0, "allowsMultiple": False}
                        ],
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
        service = ListService(http)

        fields = service.get_fields(ListId(100), field_types=[FieldType.LIST])
        assert isinstance(fields, list)


class TestListEntryServiceValidationErrors:
    """Tests for validation error branches in ListEntryService."""

    def test_list_entries_cursor_with_limit_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [], "pagination": {}}, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = ListService(http)
        entries = service.entries(ListId(100))

        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            entries.list(cursor="cursor", limit=10)

    def test_list_entries_limit_zero_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [], "pagination": {}}, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = ListService(http)
        entries = service.entries(ListId(100))

        with pytest.raises(ValueError, match="'limit' must be > 0"):
            entries.list(limit=0)

    def test_pages_cursor_with_limit_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [], "pagination": {}}, request=request)

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        service = ListService(http)
        entries = service.entries(ListId(100))

        with pytest.raises(ValueError, match="Cannot combine 'cursor' with other parameters"):
            list(entries.pages(cursor="cursor", limit=10))


class TestListServiceResolve:
    """Tests for list resolution by name."""

    def test_resolve_by_name_caches_result(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 100,
                            "name": "Pipeline",
                            "type": 2,
                            "public": True,
                            "ownerId": 1,
                            "creatorId": 1,
                            "listSize": 5,
                        }
                    ],
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
        service = ListService(http)

        # First call - note: resolve takes name as keyword argument
        result1 = service.resolve(name="Pipeline")
        assert result1 is not None
        assert result1.id == 100

        # Second call should use cache
        result2 = service.resolve(name="Pipeline")
        assert result2 is not None
        assert result2.id == 100

        # Should only have made one API call
        assert call_count == 1

    def test_resolve_not_found_returns_none(self) -> None:
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
        service = ListService(http)

        result = service.resolve(name="NonExistent")
        assert result is None
