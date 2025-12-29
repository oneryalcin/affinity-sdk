from __future__ import annotations

import httpx
import pytest

from affinity.client import ClientConfig
from affinity.clients.http import AsyncHTTPClient, HTTPClient
from affinity.exceptions import AffinityError
from affinity.models.types import CompanyId, ListId, OpportunityId, PersonId
from affinity.services.opportunities import AsyncOpportunityService, OpportunityService


def _list_entries_payload(*, list_id: int) -> dict[str, object]:
    return {
        "data": [
            {
                "id": 1,
                "listId": list_id,
                "createdAt": "2024-01-01T00:00:00Z",
                "type": "opportunity",
                "entity": {"id": 100, "name": "Deal A", "listId": list_id},
            },
            {
                "id": 2,
                "listId": list_id,
                "createdAt": "2024-01-02T00:00:00Z",
                "type": "opportunity",
                "entity": {"id": 101, "name": "Deal A", "listId": list_id},
            },
            {
                "id": 3,
                "listId": list_id,
                "createdAt": "2024-01-03T00:00:00Z",
                "type": "opportunity",
                "entity": {"id": 102, "name": "Deal B", "listId": list_id},
            },
        ],
        "pagination": {"nextUrl": None, "prevUrl": None},
    }


def test_opportunity_service_resolve_and_resolve_all() -> None:
    list_id = 41780

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            f"https://v2.example/v2/lists/{list_id}/list-entries"
        ):
            return httpx.Response(200, json=_list_entries_payload(list_id=list_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        resolved = svc.resolve(name="Deal A", list_id=ListId(list_id))
        assert resolved is not None
        assert resolved.id == OpportunityId(100)

        matches = svc.resolve_all(name="Deal A", list_id=ListId(list_id))
        assert [m.id for m in matches] == [OpportunityId(100), OpportunityId(101)]

        missing = svc.resolve(name="Missing", list_id=ListId(list_id))
        assert missing is None
    finally:
        http.close()


async def test_async_opportunity_service_resolve_and_resolve_all() -> None:
    list_id = 41780

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            f"https://v2.example/v2/lists/{list_id}/list-entries"
        ):
            return httpx.Response(200, json=_list_entries_payload(list_id=list_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        resolved = await svc.resolve(name="Deal A", list_id=ListId(list_id))
        assert resolved is not None
        assert resolved.id == OpportunityId(100)

        matches = await svc.resolve_all(name="Deal A", list_id=ListId(list_id))
        assert [m.id for m in matches] == [OpportunityId(100), OpportunityId(101)]

        missing = await svc.resolve(name="Missing", list_id=ListId(list_id))
        assert missing is None
    finally:
        await http.close()


# =============================================================================
# Association Methods Tests (FR-004: V1-only fallback)
# =============================================================================


def _v1_opportunity_payload(opp_id: int) -> dict[str, object]:
    """V1 opportunity with person and organization associations."""
    return {
        "id": opp_id,
        "name": f"Opportunity {opp_id}",
        "list_id": 123,
        "person_ids": [1001, 1002],
        "organization_ids": [2001],
    }


def _v1_person_payload(person_id: int) -> dict[str, object]:
    """V1 person response."""
    return {
        "id": person_id,
        "first_name": f"Person{person_id}",
        "last_name": "Test",
        "emails": [f"person{person_id}@example.com"],
        "type": 1,  # external
    }


def _v1_organization_payload(org_id: int) -> dict[str, object]:
    """V1 organization response."""
    return {
        "id": org_id,
        "name": f"Company {org_id}",
        "domain": f"company{org_id}.com",
    }


@pytest.mark.req("FR-004")
def test_get_associated_person_ids() -> None:
    """Test get_associated_person_ids returns PersonId list from V1 API."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        person_ids = svc.get_associated_person_ids(OpportunityId(opp_id))
        assert person_ids == [PersonId(1001), PersonId(1002)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_person_ids_with_max_results() -> None:
    """Test get_associated_person_ids respects max_results."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        person_ids = svc.get_associated_person_ids(OpportunityId(opp_id), max_results=1)
        assert person_ids == [PersonId(1001)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_people() -> None:
    """Test get_associated_people returns full Person objects."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == f"https://v1.example/opportunities/{opp_id}":
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        if request.method == "GET" and url == "https://v1.example/persons/1001":
            return httpx.Response(200, json=_v1_person_payload(1001), request=request)
        if request.method == "GET" and url == "https://v1.example/persons/1002":
            return httpx.Response(200, json=_v1_person_payload(1002), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        people = svc.get_associated_people(OpportunityId(opp_id))
        assert len(people) == 2
        assert people[0].id == PersonId(1001)
        assert people[1].id == PersonId(1002)
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_company_ids() -> None:
    """Test get_associated_company_ids returns CompanyId list from V1 API."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        company_ids = svc.get_associated_company_ids(OpportunityId(opp_id))
        assert company_ids == [CompanyId(2001)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_companies() -> None:
    """Test get_associated_companies returns full Company objects."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == f"https://v1.example/opportunities/{opp_id}":
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        if request.method == "GET" and url == "https://v1.example/organizations/2001":
            return httpx.Response(200, json=_v1_organization_payload(2001), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        companies = svc.get_associated_companies(OpportunityId(opp_id))
        assert len(companies) == 1
        assert companies[0].id == CompanyId(2001)
        assert companies[0].name == "Company 2001"
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associations() -> None:
    """Test get_associations returns OpportunityAssociations named tuple."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        assoc = svc.get_associations(OpportunityId(opp_id))
        assert assoc.person_ids == [PersonId(1001), PersonId(1002)]
        assert assoc.company_ids == [CompanyId(2001)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_person_ids_batch() -> None:
    """Test get_associated_person_ids_batch returns dict mapping opp_id -> person_ids."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == "https://v1.example/opportunities/100":
            return httpx.Response(200, json=_v1_opportunity_payload(100), request=request)
        if request.method == "GET" and url == "https://v1.example/opportunities/101":
            return httpx.Response(
                200,
                json={
                    "id": 101,
                    "name": "Opp 101",
                    "list_id": 123,
                    "person_ids": [3001],
                    "organization_ids": [],
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        result = svc.get_associated_person_ids_batch([OpportunityId(100), OpportunityId(101)])
        assert result[OpportunityId(100)] == [PersonId(1001), PersonId(1002)]
        assert result[OpportunityId(101)] == [PersonId(3001)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_person_ids_batch_on_error_raise() -> None:
    """Test get_associated_person_ids_batch raises AffinityError when on_error='raise'."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == "https://v1.example/opportunities/100":
            return httpx.Response(200, json=_v1_opportunity_payload(100), request=request)
        if request.method == "GET" and url == "https://v1.example/opportunities/999":
            return httpx.Response(404, json={"message": "not found"}, request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        with pytest.raises(AffinityError):
            svc.get_associated_person_ids_batch(
                [OpportunityId(100), OpportunityId(999)],
                on_error="raise",
            )
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_person_ids_batch_on_error_skip() -> None:
    """Test get_associated_person_ids_batch skips failed IDs when on_error='skip'."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == "https://v1.example/opportunities/100":
            return httpx.Response(200, json=_v1_opportunity_payload(100), request=request)
        if request.method == "GET" and url == "https://v1.example/opportunities/999":
            return httpx.Response(404, json={"message": "not found"}, request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        result = svc.get_associated_person_ids_batch(
            [OpportunityId(100), OpportunityId(999)],
            on_error="skip",
        )
        # Only successful fetch is included
        assert OpportunityId(100) in result
        assert OpportunityId(999) not in result
        assert result[OpportunityId(100)] == [PersonId(1001), PersonId(1002)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_person_ids_handles_camelCase() -> None:
    """Test get_associated_person_ids handles camelCase response keys."""
    opp_id = 100
    camel_case_payload = {
        "id": opp_id,
        "name": "Opportunity",
        "listId": 123,
        "personIds": [1001, 1002],  # camelCase
        "organizationIds": [2001],  # camelCase
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=camel_case_payload, request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        person_ids = svc.get_associated_person_ids(OpportunityId(opp_id))
        assert person_ids == [PersonId(1001), PersonId(1002)]
    finally:
        http.close()


@pytest.mark.req("FR-004")
def test_get_associated_person_ids_empty_when_missing() -> None:
    """Test get_associated_person_ids returns empty list when no associations."""
    opp_id = 100
    empty_payload = {
        "id": opp_id,
        "name": "Opportunity",
        "listId": 123,
        # No person_ids or organization_ids
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=empty_payload, request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = OpportunityService(http)
        person_ids = svc.get_associated_person_ids(OpportunityId(opp_id))
        assert person_ids == []
    finally:
        http.close()


# =============================================================================
# Async Association Methods Tests
# =============================================================================


@pytest.mark.req("FR-004")
async def test_async_get_associated_person_ids() -> None:
    """Test async get_associated_person_ids returns PersonId list from V1 API."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        person_ids = await svc.get_associated_person_ids(OpportunityId(opp_id))
        assert person_ids == [PersonId(1001), PersonId(1002)]
    finally:
        await http.close()


@pytest.mark.req("FR-004")
async def test_async_get_associated_people() -> None:
    """Test async get_associated_people returns full Person objects."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == f"https://v1.example/opportunities/{opp_id}":
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        if request.method == "GET" and url == "https://v1.example/persons/1001":
            return httpx.Response(200, json=_v1_person_payload(1001), request=request)
        if request.method == "GET" and url == "https://v1.example/persons/1002":
            return httpx.Response(200, json=_v1_person_payload(1002), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        people = await svc.get_associated_people(OpportunityId(opp_id))
        assert len(people) == 2
        assert people[0].id == PersonId(1001)
        assert people[1].id == PersonId(1002)
    finally:
        await http.close()


@pytest.mark.req("FR-004")
async def test_async_get_associated_company_ids() -> None:
    """Test async get_associated_company_ids returns CompanyId list from V1 API."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        company_ids = await svc.get_associated_company_ids(OpportunityId(opp_id))
        assert company_ids == [CompanyId(2001)]
    finally:
        await http.close()


@pytest.mark.req("FR-004")
async def test_async_get_associated_companies() -> None:
    """Test async get_associated_companies returns full Company objects."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == f"https://v1.example/opportunities/{opp_id}":
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        if request.method == "GET" and url == "https://v1.example/organizations/2001":
            return httpx.Response(200, json=_v1_organization_payload(2001), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        companies = await svc.get_associated_companies(OpportunityId(opp_id))
        assert len(companies) == 1
        assert companies[0].id == CompanyId(2001)
        assert companies[0].name == "Company 2001"
    finally:
        await http.close()


@pytest.mark.req("FR-004")
async def test_async_get_associations() -> None:
    """Test async get_associations returns OpportunityAssociations named tuple."""
    opp_id = 100

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/opportunities/{opp_id}"
        ):
            return httpx.Response(200, json=_v1_opportunity_payload(opp_id), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        assoc = await svc.get_associations(OpportunityId(opp_id))
        assert assoc.person_ids == [PersonId(1001), PersonId(1002)]
        assert assoc.company_ids == [CompanyId(2001)]
    finally:
        await http.close()


@pytest.mark.req("FR-004")
async def test_async_get_associated_person_ids_batch() -> None:
    """Test async get_associated_person_ids_batch returns dict mapping opp_id -> person_ids."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == "https://v1.example/opportunities/100":
            return httpx.Response(200, json=_v1_opportunity_payload(100), request=request)
        if request.method == "GET" and url == "https://v1.example/opportunities/101":
            return httpx.Response(
                200,
                json={
                    "id": 101,
                    "name": "Opp 101",
                    "list_id": 123,
                    "person_ids": [3001],
                    "organization_ids": [],
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        result = await svc.get_associated_person_ids_batch([OpportunityId(100), OpportunityId(101)])
        assert result[OpportunityId(100)] == [PersonId(1001), PersonId(1002)]
        assert result[OpportunityId(101)] == [PersonId(3001)]
    finally:
        await http.close()


@pytest.mark.req("FR-004")
async def test_async_get_associated_person_ids_batch_on_error_skip() -> None:
    """Test async get_associated_person_ids_batch skips failed IDs when on_error='skip'."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == "https://v1.example/opportunities/100":
            return httpx.Response(200, json=_v1_opportunity_payload(100), request=request)
        if request.method == "GET" and url == "https://v1.example/opportunities/999":
            return httpx.Response(404, json={"message": "not found"}, request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        svc = AsyncOpportunityService(http)
        result = await svc.get_associated_person_ids_batch(
            [OpportunityId(100), OpportunityId(999)],
            on_error="skip",
        )
        # Only successful fetch is included
        assert OpportunityId(100) in result
        assert OpportunityId(999) not in result
        assert result[OpportunityId(100)] == [PersonId(1001), PersonId(1002)]
    finally:
        await http.close()
