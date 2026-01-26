"""Tests for with_interaction_dates and with_interaction_persons parameters.

Tests cover Phase 0 of the expand-interactions implementation plan:
- CompanyService.get() with interaction params
- PersonService.get() with interaction params
- Both sync and async variants
"""

from __future__ import annotations

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.models.types import CompanyId, PersonId
from affinity.services.companies import CompanyService
from affinity.services.persons import PersonService

# =============================================================================
# CompanyService Tests
# =============================================================================


class TestCompanyServiceGetWithInteractionDates:
    """Tests for CompanyService.get() with interaction date params."""

    def test_get_with_interaction_dates_uses_v1_api(self) -> None:
        """Test that with_interaction_dates=True routes to V1 API (/organizations)."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            # V1 API uses /organizations/{id}
            if "/organizations/123" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Test Company",
                        "domain": "test.com",
                        "interaction_dates": {
                            "last_event_date": "2026-01-10T10:00:00Z",
                            "next_event_date": "2026-01-20T14:00:00Z",
                        },
                        "interactions": {
                            "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1, 2]},
                            "next_event": {"date": "2026-01-20T14:00:00Z", "person_ids": [3]},
                        },
                    },
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
        service = CompanyService(http)

        company = service.get(CompanyId(123), with_interaction_dates=True)

        # Verify it used V1 API path
        assert len(requests_made) == 1
        assert "/organizations/123" in str(requests_made[0].url)
        assert "with_interaction_dates=true" in str(requests_made[0].url).lower()

        # Verify data was populated
        assert company.id == 123
        assert company.name == "Test Company"
        assert company.interaction_dates is not None
        assert company.interactions is not None

    def test_get_with_interaction_dates_returns_interaction_data(self) -> None:
        """Test that interaction_dates and interactions are populated."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "name": "Test Company",
                    "domain": "test.com",
                    "interaction_dates": {
                        "first_email_date": "2025-01-01T08:00:00Z",
                        "last_email_date": "2026-01-10T09:30:00Z",
                        "last_event_date": "2026-01-10T10:00:00Z",
                        "next_event_date": "2026-01-20T14:00:00Z",
                        "last_interaction_date": "2026-01-10T10:00:00Z",
                    },
                    "interactions": {
                        "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1, 2]},
                        "next_event": {"date": "2026-01-20T14:00:00Z", "person_ids": [3]},
                        "last_email": {"date": "2026-01-10T09:30:00Z", "person_ids": [1]},
                    },
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
        service = CompanyService(http)

        company = service.get(CompanyId(123), with_interaction_dates=True)

        # Verify interaction_dates
        assert company.interaction_dates is not None
        assert company.interaction_dates.last_event_date is not None
        assert company.interaction_dates.next_event_date is not None
        assert company.interaction_dates.last_email_date is not None
        assert company.interaction_dates.last_interaction_date is not None

        # Verify interactions model
        assert company.interactions is not None
        assert company.interactions.last_event is not None
        assert company.interactions.last_event.person_ids == [1, 2]

    def test_get_with_interaction_persons_includes_person_ids(self) -> None:
        """Test that person_ids are included in interactions."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "name": "Test Company",
                    "domain": "test.com",
                    "interaction_dates": {"last_event_date": "2026-01-10T10:00:00Z"},
                    "interactions": {
                        "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1, 2, 3]},
                    },
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
        service = CompanyService(http)

        company = service.get(
            CompanyId(123),
            with_interaction_dates=True,
            with_interaction_persons=True,
        )

        # Verify params were passed
        assert len(requests_made) == 1
        url_str = str(requests_made[0].url).lower()
        assert "with_interaction_dates=true" in url_str
        assert "with_interaction_persons=true" in url_str

        # Verify person_ids in interactions
        assert company.interactions is not None
        assert company.interactions.last_event is not None
        assert company.interactions.last_event.person_ids == [1, 2, 3]

    def test_get_without_interaction_dates_uses_v2_api(self) -> None:
        """Test that default get() still uses V2 API."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            # V2 API uses /companies/{id}
            if "/companies/123" in str(request.url):
                return httpx.Response(
                    200,
                    json={"id": 123, "name": "Test Company", "domain": "test.com"},
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
        service = CompanyService(http)

        company = service.get(CompanyId(123))

        # Verify it used V2 API path
        assert len(requests_made) == 1
        assert "/companies/123" in str(requests_made[0].url)
        assert "organizations" not in str(requests_made[0].url)

        assert company.id == 123
        # interaction_dates should be None when not requested
        assert company.interaction_dates is None

    def test_get_with_interaction_dates_and_field_ids_makes_two_calls(self) -> None:
        """Test that field_ids with with_interaction_dates makes two API calls and merges."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            url_str = str(request.url)
            # V1 call for interaction data
            if "/organizations/123" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Test Company",
                        "domain": "test.com",
                        "interaction_dates": {"last_event_date": "2026-01-10T10:00:00Z"},
                        "interactions": {"last_event": {"person_ids": [1, 2]}},
                    },
                    request=request,
                )
            # V2 call for filtered fields
            if "/companies/123" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Test Company",
                        "domain": "test.com",
                        "fields": {"data": [{"id": "field-123", "value": "test"}]},
                    },
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
        service = CompanyService(http)

        # Combining interaction_dates with field_ids now makes two calls
        company = service.get(
            CompanyId(123),
            field_ids=["field-123"],
            with_interaction_dates=True,
        )

        # Verify both APIs were called
        assert len(requests_made) == 2
        urls = [str(r.url) for r in requests_made]
        assert any("/organizations/123" in u for u in urls)  # V1 for interactions
        assert any("/companies/123" in u and "fieldIds" in u for u in urls)  # V2 for fields

        # Result should have both interaction data and be from merged response
        assert company.id == 123
        assert company.interaction_dates is not None
        assert company.interaction_dates.last_event_date is not None


# =============================================================================
# PersonService Tests
# =============================================================================


class TestPersonServiceGetWithInteractionDates:
    """Tests for PersonService.get() with interaction date params."""

    def test_get_with_interaction_dates_uses_v1_api(self) -> None:
        """Test that with_interaction_dates=True routes to V1 API."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            # V1 API for persons
            if "/persons/456" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "id": 456,
                        "first_name": "John",
                        "last_name": "Doe",
                        "interaction_dates": {
                            "last_event_date": "2026-01-10T10:00:00Z",
                            "next_event_date": "2026-01-20T14:00:00Z",
                        },
                        "interactions": {
                            "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1]},
                        },
                    },
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
        service = PersonService(http)

        person = service.get(PersonId(456), with_interaction_dates=True)

        # Verify V1 API was used with params
        assert len(requests_made) == 1
        url_str = str(requests_made[0].url).lower()
        assert "/persons/456" in url_str
        assert "with_interaction_dates=true" in url_str
        # Check it used V1 base URL
        assert "v1.example" in url_str

        # Verify data
        assert person.id == 456
        assert person.first_name == "John"
        assert person.interaction_dates is not None
        assert person.interactions is not None

    def test_get_with_both_include_field_values_and_interaction_dates(self) -> None:
        """Test that both flags work together (both use V1 API)."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            return httpx.Response(
                200,
                json={
                    "id": 456,
                    "first_name": "John",
                    "last_name": "Doe",
                    "field_values": [
                        {"id": 99, "field_id": 1, "value": "test value"},
                    ],
                    "interaction_dates": {
                        "last_event_date": "2026-01-10T10:00:00Z",
                    },
                    "interactions": {
                        "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1]},
                    },
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
        service = PersonService(http)

        person = service.get(
            PersonId(456),
            include_field_values=True,
            with_interaction_dates=True,
        )

        # Verify only 1 API call (both use V1)
        assert len(requests_made) == 1
        url_str = str(requests_made[0].url).lower()
        assert "v1.example" in url_str
        assert "with_interaction_dates=true" in url_str

        # Verify both data types were returned
        assert person.interaction_dates is not None
        assert hasattr(person, "field_values")
        assert len(person.field_values) == 1
        assert person.field_values[0].value == "test value"

    def test_get_without_interaction_dates_uses_v2_api(self) -> None:
        """Test that default get() still uses V2 API."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            # V2 API
            if "v2.example" in str(request.url):
                return httpx.Response(
                    200,
                    json={"id": 456, "firstName": "John", "lastName": "Doe"},
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
        service = PersonService(http)

        person = service.get(PersonId(456))

        # Verify V2 API was used
        assert len(requests_made) == 1
        assert "v2.example" in str(requests_made[0].url)

        assert person.id == 456
        assert person.interaction_dates is None


# =============================================================================
# Async Service Tests
# =============================================================================


class TestAsyncCompanyServiceGetWithInteractionDates:
    """Tests for AsyncCompanyService.get() with interaction date params."""

    @pytest.mark.asyncio
    async def test_async_get_with_interaction_dates(self) -> None:
        """Test async variant with interaction dates."""
        from affinity.clients.http import AsyncHTTPClient
        from affinity.services.companies import AsyncCompanyService

        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "name": "Test Company",
                    "domain": "test.com",
                    "interaction_dates": {
                        "last_event_date": "2026-01-10T10:00:00Z",
                    },
                    "interactions": {
                        "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1]},
                    },
                },
                request=request,
            )

        http = AsyncHTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                async_transport=httpx.MockTransport(handler),
            )
        )
        try:
            service = AsyncCompanyService(http)

            company = await service.get(CompanyId(123), with_interaction_dates=True)

            # Verify V1 API was used
            assert len(requests_made) == 1
            url_str = str(requests_made[0].url).lower()
            assert "/organizations/123" in url_str
            assert "with_interaction_dates=true" in url_str

            assert company.interaction_dates is not None
            assert company.interactions is not None
        finally:
            await http.close()


class TestAsyncPersonServiceGetWithInteractionDates:
    """Tests for AsyncPersonService.get() with interaction date params."""

    @pytest.mark.asyncio
    async def test_async_get_with_interaction_dates(self) -> None:
        """Test async variant with interaction dates."""
        from affinity.clients.http import AsyncHTTPClient
        from affinity.services.persons import AsyncPersonService

        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            return httpx.Response(
                200,
                json={
                    "id": 456,
                    "first_name": "John",
                    "last_name": "Doe",
                    "interaction_dates": {
                        "last_event_date": "2026-01-10T10:00:00Z",
                    },
                    "interactions": {
                        "last_event": {"date": "2026-01-10T10:00:00Z", "person_ids": [1]},
                    },
                },
                request=request,
            )

        http = AsyncHTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                async_transport=httpx.MockTransport(handler),
            )
        )
        try:
            service = AsyncPersonService(http)

            person = await service.get(PersonId(456), with_interaction_dates=True)

            # Verify V1 API was used
            assert len(requests_made) == 1
            url_str = str(requests_made[0].url).lower()
            assert "/persons/456" in url_str
            assert "with_interaction_dates=true" in url_str

            assert person.interaction_dates is not None
            assert person.interactions is not None
        finally:
            await http.close()


# =============================================================================
# Model Tests
# =============================================================================


class TestCompanyModelWithInteractions:
    """Test that Company model correctly parses interactions field."""

    def test_company_model_parses_interactions(self) -> None:
        """Test that Company.interactions is correctly parsed."""
        from affinity.models import Company

        data = {
            "id": 123,
            "name": "Test Company",
            "domain": "test.com",
            "interaction_dates": {
                "last_event_date": "2026-01-10T10:00:00Z",
                "next_event_date": "2026-01-20T14:00:00Z",
                "last_email_date": "2026-01-09T08:00:00Z",
            },
            "interactions": {
                "last_event": {
                    "date": "2026-01-10T10:00:00Z",
                    "person_ids": [1, 2, 3],
                },
                "next_event": {
                    "date": "2026-01-20T14:00:00Z",
                    "person_ids": [4],
                },
                "last_email": {
                    "date": "2026-01-09T08:00:00Z",
                    "person_ids": [1],
                },
            },
        }

        company = Company.model_validate(data)

        assert company.id == 123
        assert company.interactions is not None
        assert company.interactions.last_event is not None
        assert company.interactions.last_event.person_ids == [1, 2, 3]
        assert company.interactions.next_event is not None
        assert company.interactions.next_event.person_ids == [4]

    def test_company_model_without_interactions(self) -> None:
        """Test that Company works without interactions field."""
        from affinity.models import Company

        data = {
            "id": 123,
            "name": "Test Company",
            "domain": "test.com",
        }

        company = Company.model_validate(data)

        assert company.id == 123
        assert company.interactions is None
        assert company.interaction_dates is None
