"""Tests for service.get() parameter combinations.

Tests the behavior when combining with_interaction_dates, field_ids, field_types,
and include_field_values parameters.
"""

from __future__ import annotations

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.models.types import CompanyId, FieldType, PersonId
from affinity.services.companies import CompanyService
from affinity.services.persons import PersonService


class TestCompanyServiceGetParameterCombinations:
    """Tests for CompanyService.get() parameter combinations."""

    def test_with_interaction_dates_alone_uses_single_call(self) -> None:
        """with_interaction_dates alone should make one V1 API call."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/organizations/123" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Acme Corp",
                        "domain": "acme.com",
                        "interaction_dates": {
                            "last_event_date": "2026-01-10T10:00:00Z",
                        },
                        "interactions": {"last_event": {"person_ids": [1, 2]}},
                    },
                    request=request,
                )
            raise ValueError(f"Unexpected request: {request.url}")

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            svc = CompanyService(http)
            company = svc.get(CompanyId(123), with_interaction_dates=True)

            assert company.id == CompanyId(123)
            assert company.interaction_dates is not None
            assert len(calls) == 1
            assert "organizations/123" in calls[0]
        finally:
            http.close()

    def test_with_interaction_dates_and_field_ids_makes_two_calls(self) -> None:
        """with_interaction_dates + field_ids should make two API calls and merge."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            # V1 call for interaction data
            if "/organizations/123" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Acme Corp",
                        "interaction_dates": {
                            "last_event_date": "2026-01-10T10:00:00Z",
                        },
                        "interactions": {"last_event": {"person_ids": [1, 2]}},
                    },
                    request=request,
                )
            # V2 call for filtered fields
            if "/companies/123" in str(request.url):
                assert "fieldIds=field-1" in str(request.url)
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Acme Corp",
                        "domain": "acme.com",
                        "fields": {"data": [{"id": "field-1", "value": "test"}]},
                    },
                    request=request,
                )
            raise ValueError(f"Unexpected request: {request.url}")

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            svc = CompanyService(http)
            company = svc.get(
                CompanyId(123),
                with_interaction_dates=True,
                field_ids=["field-1"],
            )

            # Should have both interaction data and filtered fields
            assert company.id == CompanyId(123)
            assert company.interaction_dates is not None
            assert company.interaction_dates.last_event_date is not None
            # Two API calls: V1 for interactions, V2 for filtered fields
            assert len(calls) == 2
            assert any("organizations/123" in c for c in calls)
            assert any("companies/123" in c for c in calls)
        finally:
            http.close()

    def test_with_interaction_dates_and_field_types_makes_two_calls(self) -> None:
        """with_interaction_dates + field_types should make two API calls and merge."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/organizations/123" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Acme Corp",
                        "interaction_dates": {"last_email_date": "2026-01-12T09:00:00Z"},
                    },
                    request=request,
                )
            if "/companies/123" in str(request.url):
                assert "fieldTypes=global" in str(request.url)
                return httpx.Response(
                    200,
                    json={
                        "id": 123,
                        "name": "Acme Corp",
                        "fields": {"data": []},
                    },
                    request=request,
                )
            raise ValueError(f"Unexpected request: {request.url}")

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            svc = CompanyService(http)
            company = svc.get(
                CompanyId(123),
                with_interaction_dates=True,
                field_types=[FieldType.GLOBAL],
            )

            assert company.interaction_dates is not None
            assert len(calls) == 2
        finally:
            http.close()


class TestPersonServiceGetParameterCombinations:
    """Tests for PersonService.get() parameter combinations."""

    def test_include_field_values_with_field_ids_raises_error(self) -> None:
        """include_field_values + field_ids should raise ValueError."""
        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(lambda _: httpx.Response(200)),
            )
        )
        try:
            svc = PersonService(http)
            with pytest.raises(ValueError, match="Cannot combine 'include_field_values'"):
                svc.get(
                    PersonId(1),
                    include_field_values=True,
                    field_ids=["field-1"],
                )
        finally:
            http.close()

    def test_include_field_values_with_field_types_raises_error(self) -> None:
        """include_field_values + field_types should raise ValueError."""
        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(lambda _: httpx.Response(200)),
            )
        )
        try:
            svc = PersonService(http)
            with pytest.raises(ValueError, match="Cannot combine 'include_field_values'"):
                svc.get(
                    PersonId(1),
                    include_field_values=True,
                    field_types=[FieldType.GLOBAL],
                )
        finally:
            http.close()

    def test_with_interaction_dates_and_field_ids_makes_two_calls(self) -> None:
        """with_interaction_dates + field_ids should make two API calls and merge."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            # V1 call for interaction data
            if "v1.example/persons/456" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "id": 456,
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "emails": ["alice@example.com"],
                        "type": "external",
                        "interaction_dates": {
                            "last_event_date": "2026-01-10T10:00:00Z",
                        },
                        "interactions": {"last_event": {"person_ids": [1, 2]}},
                    },
                    request=request,
                )
            # V2 call for filtered fields
            if "v2.example/v2/persons/456" in str(request.url):
                assert "fieldIds=field-1" in str(request.url)
                return httpx.Response(
                    200,
                    json={
                        "id": 456,
                        "firstName": "Alice",
                        "lastName": "Smith",
                        "emails": ["alice@example.com"],
                        "type": "external",
                        "fields": {"data": [{"id": "field-1", "value": "test"}]},
                    },
                    request=request,
                )
            raise ValueError(f"Unexpected request: {request.url}")

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            svc = PersonService(http)
            person = svc.get(
                PersonId(456),
                with_interaction_dates=True,
                field_ids=["field-1"],
            )

            # Should have both interaction data and filtered fields
            assert person.id == PersonId(456)
            assert person.interaction_dates is not None
            assert person.interaction_dates.last_event_date is not None
            # Two API calls: V1 for interactions, V2 for filtered fields
            assert len(calls) == 2
        finally:
            http.close()

    def test_include_field_values_with_interaction_dates_works(self) -> None:
        """include_field_values + with_interaction_dates should work (single V1 call)."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/persons/456" in str(request.url):
                assert "with_interaction_dates=True" in str(request.url)
                return httpx.Response(
                    200,
                    json={
                        "id": 456,
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "emails": ["alice@example.com"],
                        "type": "external",
                        "interaction_dates": {
                            "last_event_date": "2026-01-10T10:00:00Z",
                        },
                        "field_values": [{"id": 99, "field_id": 1, "value": "test"}],
                    },
                    request=request,
                )
            raise ValueError(f"Unexpected request: {request.url}")

        http = HTTPClient(
            ClientConfig(
                api_key="test",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            svc = PersonService(http)
            person = svc.get(
                PersonId(456),
                include_field_values=True,
                with_interaction_dates=True,
            )

            assert person.id == PersonId(456)
            assert person.interaction_dates is not None
            assert hasattr(person, "field_values")
            # Single V1 call returns both
            assert len(calls) == 1
        finally:
            http.close()
