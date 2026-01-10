from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from affinity.clients.http import AsyncHTTPClient, ClientConfig, HTTPClient
from affinity.exceptions import BetaEndpointDisabledError
from affinity.models import CompanyCreate, CompanyUpdate, PersonCreate, PersonUpdate
from affinity.models.secondary import MergeTask
from affinity.models.types import (
    CompanyId,
    FieldType,
    ListEntryId,
    ListId,
    ListType,
    OpportunityId,
    PersonId,
    PersonType,
)
from affinity.services.companies import AsyncCompanyService, CompanyService
from affinity.services.persons import AsyncPersonService, PersonService


def test_person_service_v2_read_v1_write_resolve_merge_and_cache_invalidation() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
    calls: dict[str, int] = {"person_fields": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/persons?cursor=abc"):
            return httpx.Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/persons"
        ):
            field_ids = url.params.get_list("fieldIds")
            if field_ids:
                assert field_ids == ["field-1"]
            field_types = url.params.get_list("fieldTypes")
            if field_types:
                assert field_types == ["global"]
            filter_text = url.params.get("filter")
            if filter_text is not None:
                assert filter_text == "x"
            limit = url.params.get("limit")
            if limit is not None:
                assert limit == "1"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "firstName": "A",
                            "lastName": "B",
                            "primaryEmailAddress": "a@example.com",
                            "emails": ["a@example.com"],
                            "type": "external",
                        }
                    ],
                    "pagination": {"nextUrl": "https://v2.example/v2/persons?cursor=abc"},
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/persons/1"
        ):
            assert url.params.get_list("fieldIds") == ["field-1"]
            assert url.params.get_list("fieldTypes") == ["global"]
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": ["a@example.com", "alt@example.com"],
                    "type": "external",
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/persons/1/list-entries"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "listId": 10, "createdAt": created_at, "fields": {}}],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/persons/1/lists"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 10,
                            "name": "L",
                            "type": 0,
                            "public": True,
                            "ownerId": 1,
                            "listSize": 0,
                        }
                    ],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/persons/fields"
        ):
            calls["person_fields"] += 1
            field_types = url.params.get_list("fieldTypes")
            if field_types:
                assert field_types == ["global"]
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "field-1",
                            "name": "F",
                            "valueType": 2,
                            "allowsMultiple": False,
                            "type": "global",
                        }
                    ]
                },
                request=request,
            )

        if request.method == "POST" and url == httpx.URL("https://v2.example/v2/person-merges"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"primaryPersonId": 1, "duplicatePersonId": 2}
            return httpx.Response(
                200,
                json={"taskUrl": "https://v2.example/v2/tasks/person-merges/1"},
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/tasks/person-merges/1"
        ):
            return httpx.Response(
                200,
                json={"id": "1", "status": "success", "resultsSummary": None},
                request=request,
            )

        # V1 search + write operations
        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            assert url.params.get("term") in {
                "a@example.com",
                "alt@example.com",
                "A B",
                "missing@example.com",
                "x",
            }
            return httpx.Response(
                200,
                json={
                    "persons": [
                        {
                            "id": 1,
                            "firstName": "A",
                            "lastName": "B",
                            "primaryEmailAddress": "a@example.com",
                            "emails": ["alt@example.com"],
                            "type": "external",
                        }
                    ],
                    "next_page_token": None,
                },
                request=request,
            )

        if request.method == "POST" and url == httpx.URL("https://v1.example/persons"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload in (
                {"first_name": "A", "last_name": "B", "emails": ["a@example.com"]},
                {
                    "first_name": "A",
                    "last_name": "B",
                    "emails": ["a@example.com"],
                    "organization_ids": [2],
                },
            )
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": ["a@example.com"],
                    "type": "external",
                },
                request=request,
            )

        if request.method == "PUT" and url == httpx.URL("https://v1.example/persons/1"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload in (
                {"first_name": "A2"},
                {
                    "first_name": "A2",
                    "last_name": "B2",
                    "emails": ["a@example.com"],
                    "organization_ids": [2],
                },
            )
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A2",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": ["a@example.com"],
                    "type": "external",
                },
                request=request,
            )

        if request.method == "DELETE" and url == httpx.URL("https://v1.example/persons/1"):
            return httpx.Response(200, json={"success": True}, request=request)

        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_cache=True,
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = PersonService(http)

        page = service.list(
            field_ids=["field-1"],
            field_types=[FieldType.GLOBAL],
            filter="x",
            limit=1,
        )
        assert [p.id for p in page.data] == [PersonId(1)]
        _ = service.list(filter="  ")

        all_people = list(
            service.all(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x")
        )
        assert [p.id for p in all_people] == [PersonId(1)]
        assert [p.id for p in list(service.iter())] == [PersonId(1)]

        person = service.get(PersonId(1), field_ids=["field-1"], field_types=[FieldType.GLOBAL])
        assert person.full_name == "A B"

        entries = service.get_list_entries(PersonId(1))
        assert entries.data[0].list_id == ListId(10)

        lists = service.get_lists(PersonId(1))
        assert lists.data[0].type == ListType.PERSON

        _ = service.get_fields(field_types=[FieldType.GLOBAL])
        _ = service.get_fields(field_types=[FieldType.GLOBAL])
        assert calls["person_fields"] == 1
        _ = service.get_fields(field_types=None)

        created = service.create(
            PersonCreate(
                first_name="A",
                last_name="B",
                emails=["a@example.com"],
                company_ids=[CompanyId(2)],
            )
        )
        assert created.id == PersonId(1)
        _ = service.get_fields(field_types=[FieldType.GLOBAL])
        assert calls["person_fields"] == 3

        updated = service.update(
            PersonId(1),
            PersonUpdate(
                first_name="A2",
                last_name="B2",
                emails=["a@example.com"],
                company_ids=[CompanyId(2)],
            ),
        )
        assert updated.first_name == "A2"

        assert service.delete(PersonId(1)) is True

        searched = service.search(
            "x",
            with_interaction_dates=True,
            with_interaction_persons=True,
            with_opportunities=True,
            page_size=1,
            page_token="t",
        )
        assert searched.data[0].id == PersonId(1)
        assert service.search("x").data[0].id == PersonId(1)

        with pytest.raises(ValueError):
            service.resolve()
        assert service.resolve(email="a@example.com") is not None
        assert service.resolve(email="alt@example.com") is not None
        assert service.resolve(name="A B") is not None
        assert service.resolve(email="missing@example.com") is None
        assert service.resolve(email="missing@example.com", name="A B") is not None

        with pytest.raises(BetaEndpointDisabledError):
            service.merge(PersonId(1), PersonId(2))

        beta_http = HTTPClient(
            ClientConfig(
                api_key="k",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                enable_beta_endpoints=True,
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            beta = PersonService(beta_http)
            task_url = beta.merge(PersonId(1), PersonId(2))
            assert task_url.endswith("/tasks/person-merges/1")
            status = beta.get_merge_status("1")
            assert isinstance(status, MergeTask)
            assert status.status == "success"
        finally:
            beta_http.close()
    finally:
        http.close()


def test_person_service_resolve_paginates_and_resolve_all_collects() -> None:
    tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            token = request.url.params.get("page_token")
            tokens.append(token)
            if token is None:
                return httpx.Response(
                    200,
                    json={
                        "persons": [
                            {
                                "id": 1,
                                "firstName": "A",
                                "lastName": "B",
                                "primaryEmailAddress": "a@example.com",
                                "emails": ["a@example.com"],
                                "type": "external",
                            }
                        ],
                        "next_page_token": "page-2",
                    },
                    request=request,
                )
            if token == "page-2":
                return httpx.Response(
                    200,
                    json={
                        "persons": [
                            {
                                "id": 2,
                                "firstName": "C",
                                "lastName": "D",
                                "primaryEmailAddress": "target@example.com",
                                "emails": ["target@example.com"],
                                "type": "external",
                            }
                        ],
                        "next_page_token": None,
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
        service = PersonService(http)
        resolved = service.resolve(email="target@example.com")
        assert resolved is not None
        assert resolved.id == PersonId(2)

        matches = service.resolve_all(email="target@example.com")
        assert [person.id for person in matches] == [PersonId(2)]
        assert "page-2" in tokens
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_person_service_resolve_paginates_and_resolve_all_collects() -> None:
    tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            token = request.url.params.get("page_token")
            tokens.append(token)
            if token is None:
                return httpx.Response(
                    200,
                    json={
                        "persons": [
                            {
                                "id": 1,
                                "firstName": "A",
                                "lastName": "B",
                                "primaryEmailAddress": "a@example.com",
                                "emails": ["a@example.com"],
                                "type": "external",
                            }
                        ],
                        "next_page_token": "page-2",
                    },
                    request=request,
                )
            if token == "page-2":
                return httpx.Response(
                    200,
                    json={
                        "persons": [
                            {
                                "id": 2,
                                "firstName": "C",
                                "lastName": "D",
                                "primaryEmailAddress": "target@example.com",
                                "emails": ["target@example.com"],
                                "type": "external",
                            }
                        ],
                        "next_page_token": None,
                    },
                    request=request,
                )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = AsyncPersonService(client)
        resolved = await service.resolve(email="target@example.com")
        assert resolved is not None
        assert resolved.id == PersonId(2)

        matches = await service.resolve_all(email="target@example.com")
        assert [person.id for person in matches] == [PersonId(2)]
        assert "page-2" in tokens
    finally:
        await client.close()


def test_company_service_expansion_pagination_supports_limit_and_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if (
            request.method == "GET"
            and url.copy_with(query=None) == httpx.URL("https://v2.example/v2/companies/2/lists")
            and url.params.get("cursor") is None
        ):
            assert url.params.get("limit") == "2"
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "name": "List A"}],
                    "pagination": {"nextUrl": "https://v2.example/v2/companies/2/lists?cursor=abc"},
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/lists?cursor=abc"
        ):
            return httpx.Response(
                200,
                json={"data": [{"id": 2, "name": "List B"}], "pagination": {"nextUrl": None}},
                request=request,
            )
        if (
            request.method == "GET"
            and url.copy_with(query=None)
            == httpx.URL("https://v2.example/v2/companies/2/list-entries")
            and url.params.get("cursor") is None
        ):
            assert url.params.get("limit") == "2"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 10,
                            "listId": 1,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "fields": {},
                        }
                    ],
                    "pagination": {
                        "nextUrl": "https://v2.example/v2/companies/2/list-entries?cursor=def"
                    },
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/list-entries?cursor=def"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 11,
                            "listId": 1,
                            "createdAt": "2024-01-02T00:00:00Z",
                            "fields": {},
                        }
                    ],
                    "pagination": {"nextUrl": None},
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
        service = CompanyService(http)
        lists_page = service.get_lists(CompanyId(2), limit=2)
        assert [lst.id for lst in lists_page.data] == [ListId(1)]
        lists_next = service.get_lists(CompanyId(2), cursor=lists_page.next_cursor)
        assert [lst.id for lst in lists_next.data] == [ListId(2)]

        entries_page = service.get_list_entries(CompanyId(2), limit=2)
        assert [entry.id for entry in entries_page.data] == [ListEntryId(10)]
        entries_next = service.get_list_entries(CompanyId(2), cursor=entries_page.next_cursor)
        assert [entry.id for entry in entries_next.data] == [ListEntryId(11)]

        with pytest.raises(ValueError):
            service.get_lists(CompanyId(2), limit=1, cursor="x")
        with pytest.raises(ValueError):
            service.get_list_entries(CompanyId(2), limit=1, cursor="x")
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_company_service_expansion_pagination_supports_limit_and_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if (
            request.method == "GET"
            and url.copy_with(query=None) == httpx.URL("https://v2.example/v2/companies/2/lists")
            and url.params.get("cursor") is None
        ):
            assert url.params.get("limit") == "2"
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "name": "List A"}],
                    "pagination": {"nextUrl": "https://v2.example/v2/companies/2/lists?cursor=abc"},
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/lists?cursor=abc"
        ):
            return httpx.Response(
                200,
                json={"data": [{"id": 2, "name": "List B"}], "pagination": {"nextUrl": None}},
                request=request,
            )
        if (
            request.method == "GET"
            and url.copy_with(query=None)
            == httpx.URL("https://v2.example/v2/companies/2/list-entries")
            and url.params.get("cursor") is None
        ):
            assert url.params.get("limit") == "2"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 10,
                            "listId": 1,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "fields": {},
                        }
                    ],
                    "pagination": {
                        "nextUrl": "https://v2.example/v2/companies/2/list-entries?cursor=def"
                    },
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/list-entries?cursor=def"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 11,
                            "listId": 1,
                            "createdAt": "2024-01-02T00:00:00Z",
                            "fields": {},
                        }
                    ],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = AsyncCompanyService(client)
        lists_page = await service.get_lists(CompanyId(2), limit=2)
        assert [lst.id for lst in lists_page.data] == [ListId(1)]
        lists_next = await service.get_lists(CompanyId(2), cursor=lists_page.next_cursor)
        assert [lst.id for lst in lists_next.data] == [ListId(2)]

        entries_page = await service.get_list_entries(CompanyId(2), limit=2)
        assert [entry.id for entry in entries_page.data] == [ListEntryId(10)]
        entries_next = await service.get_list_entries(CompanyId(2), cursor=entries_page.next_cursor)
        assert [entry.id for entry in entries_next.data] == [ListEntryId(11)]

        with pytest.raises(ValueError):
            await service.get_lists(CompanyId(2), limit=1, cursor="x")
        with pytest.raises(ValueError):
            await service.get_list_entries(CompanyId(2), limit=1, cursor="x")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_person_and_company_services_cover_list_all_get() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/companies"
        ):
            if url.params.get_list("fieldIds"):
                assert url.params.get_list("fieldIds") == ["field-1"]
            if url.params.get_list("fieldTypes"):
                assert url.params.get_list("fieldTypes") == ["global"]
            if url.params.get("filter") is not None:
                assert url.params.get("filter") == "x"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": 2, "name": "Acme", "domain": "acme.com", "type": "external"},
                    ],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/companies/2"
        ):
            if url.params.get_list("fieldIds"):
                assert url.params.get_list("fieldIds") == ["field-1"]
            if url.params.get_list("fieldTypes"):
                assert url.params.get_list("fieldTypes") == ["global"]
            return httpx.Response(
                200,
                json={"id": 2, "name": "Acme", "domain": "acme.com"},
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/persons"
        ):
            cursor = url.params.get("cursor")
            if cursor is not None:
                return httpx.Response(
                    200,
                    json={"data": [], "pagination": {"nextUrl": None}},
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "firstName": "A",
                            "lastName": "B",
                            "primaryEmailAddress": "a@example.com",
                            "emails": [],
                            "type": "external",
                        }
                    ],
                    "pagination": {"nextUrl": "https://v2.example/v2/persons?cursor=abc"},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/persons?cursor=abc"):
            return httpx.Response(
                200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/persons/1"):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": [],
                    "type": "external",
                    "fields": {},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/persons/1/list-entries"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "listId": 10, "createdAt": created_at, "fields": {}}],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_beta_endpoints=True,
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        companies = AsyncCompanyService(client)
        company_page = await companies.list(
            field_ids=["field-1"],
            field_types=[FieldType.GLOBAL],
            filter="x",
            limit=1,
        )
        assert company_page.data[0].id == CompanyId(2)
        _ = await companies.list(filter=" ")
        company = await companies.get(
            CompanyId(2), field_ids=["field-1"], field_types=[FieldType.GLOBAL]
        )
        assert company.domain == "acme.com"

        persons = AsyncPersonService(client)
        person_page = await persons.list(
            field_ids=["field-1"],
            field_types=[FieldType.GLOBAL],
            filter="x",
            limit=1,
        )
        assert person_page.data[0].type == PersonType.EXTERNAL
        _ = await persons.list(filter=" ")
        all_people = [p async for p in persons.all()]
        assert [p.id for p in all_people] == [PersonId(1)]
        all_people_2 = [p async for p in persons.iter()]
        assert [p.id for p in all_people_2] == [PersonId(1)]
        single = await persons.get(PersonId(1))
        assert single.id == PersonId(1)
    finally:
        await client.close()


def test_company_service_v2_read_v1_write_resolve_merge_and_cache_invalidation() -> None:
    calls: dict[str, Any] = {"company_fields": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/companies"):
            return httpx.Response(
                200,
                json={"data": [{"id": 2, "name": "Acme", "domain": "acme.com"}], "pagination": {}},
                request=request,
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/companies/2"):
            return httpx.Response(
                200, json={"id": 2, "name": "Acme", "domain": "acme.com"}, request=request
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/companies/fields"):
            calls["company_fields"] += 1
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "field-1", "name": "F", "valueType": 2, "allowsMultiple": False}
                    ]
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v1.example/organizations"
        ):
            assert url.params.get("term") in {"acme.com", "Acme", "missing.com"}
            if url.params.get("with_interaction_dates") is not None:
                assert url.params.get("with_interaction_dates") == "True"
            if url.params.get("with_interaction_persons") is not None:
                assert url.params.get("with_interaction_persons") == "True"
            if url.params.get("with_opportunities") is not None:
                assert url.params.get("with_opportunities") == "True"
            if url.params.get("page_size") is not None:
                assert url.params.get("page_size") in {"1", "10"}
            if url.params.get("page_token") is not None:
                assert url.params.get("page_token") == "t"
            return httpx.Response(
                200,
                json={
                    "organizations": [{"id": 2, "name": "Acme", "domain": "acme.com"}],
                    "next_page_token": None,
                },
                request=request,
            )

        if request.method == "POST" and url == httpx.URL("https://v1.example/organizations"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"name": "Acme", "domain": "acme.com", "person_ids": [1]}
            return httpx.Response(
                200,
                json={"id": 2, "name": "Acme", "domain": "acme.com"},
                request=request,
            )

        if request.method == "PUT" and url == httpx.URL("https://v1.example/organizations/2"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"name": "Acme2"}
            return httpx.Response(
                200, json={"id": 2, "name": "Acme2", "domain": "acme.com"}, request=request
            )

        if request.method == "DELETE" and url == httpx.URL("https://v1.example/organizations/2"):
            return httpx.Response(200, json={"success": True}, request=request)

        if request.method == "POST" and url == httpx.URL("https://v2.example/v2/company-merges"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"primaryCompanyId": 2, "duplicateCompanyId": 3}
            return httpx.Response(
                200,
                json={"taskUrl": "https://v2.example/v2/tasks/company-merges/1"},
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/tasks/company-merges/1"
        ):
            return httpx.Response(200, json={"id": "1", "status": "success"}, request=request)

        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_cache=True,
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = CompanyService(http)
        page = service.list()
        assert page.data[0].id == CompanyId(2)
        assert next(service.all()).id == CompanyId(2)
        assert service.get(CompanyId(2)).name == "Acme"

        _ = service.get_fields(field_types=None)
        assert calls["company_fields"] == 1
        _ = service.get_fields(field_types=None)
        assert calls["company_fields"] == 1

        created = service.create(
            CompanyCreate(name="Acme", domain="acme.com", person_ids=[PersonId(1)])
        )
        assert created.id == CompanyId(2)
        _ = service.get_fields(field_types=None)
        assert calls["company_fields"] == 2

        updated = service.update(CompanyId(2), CompanyUpdate(name="Acme2"))
        assert updated.name == "Acme2"

        assert service.delete(CompanyId(2)) is True

        with pytest.raises(ValueError):
            service.resolve()
        assert service.resolve(domain="acme.com") is not None
        assert service.resolve(name="Acme") is not None
        assert service.resolve(domain="missing.com") is None
        searched = service.search(
            "Acme",
            with_interaction_dates=True,
            with_interaction_persons=True,
            with_opportunities=True,
            page_size=1,
            page_token="t",
        )
        assert searched.data[0].id == CompanyId(2)

        with pytest.raises(BetaEndpointDisabledError):
            service.merge(CompanyId(2), CompanyId(3))

        beta_http = HTTPClient(
            ClientConfig(
                api_key="k",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                enable_beta_endpoints=True,
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        try:
            beta = CompanyService(beta_http)
            task_url = beta.merge(CompanyId(2), CompanyId(3))
            assert task_url.endswith("/tasks/company-merges/1")
            status = beta.get_merge_status("1")
            assert status.status == "success"
        finally:
            beta_http.close()
    finally:
        http.close()


def test_person_and_company_write_ops_skip_cache_invalidation_when_cache_disabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "POST" and url == httpx.URL("https://v1.example/persons"):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": ["a@example.com"],
                    "type": "external",
                },
                request=request,
            )
        if request.method == "PUT" and url == httpx.URL("https://v1.example/persons/1"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {}
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": ["a@example.com"],
                    "type": "external",
                },
                request=request,
            )
        if request.method == "DELETE" and url == httpx.URL("https://v1.example/persons/1"):
            return httpx.Response(200, json={"success": True}, request=request)

        if request.method == "POST" and url == httpx.URL("https://v1.example/organizations"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"name": "Acme"}
            return httpx.Response(
                200, json={"id": 2, "name": "Acme", "domain": None}, request=request
            )
        if request.method == "PUT" and url == httpx.URL("https://v1.example/organizations/2"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"domain": "acme.com", "person_ids": []}
            return httpx.Response(
                200, json={"id": 2, "name": "Acme", "domain": "acme.com"}, request=request
            )
        if request.method == "DELETE" and url == httpx.URL("https://v1.example/organizations/2"):
            return httpx.Response(200, json={"success": True}, request=request)

        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_cache=False,
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        people = PersonService(http)
        created = people.create(
            PersonCreate(first_name="A", last_name="B", emails=["a@example.com"])
        )
        assert created.id == PersonId(1)
        _ = people.update(PersonId(1), PersonUpdate())
        assert people.delete(PersonId(1)) is True

        companies = CompanyService(http)
        created_company = companies.create(CompanyCreate(name="Acme"))
        assert created_company.id == CompanyId(2)
        _ = companies.update(CompanyId(2), CompanyUpdate(domain="acme.com", person_ids=[]))
        assert companies.delete(CompanyId(2)) is True
    finally:
        http.close()


def test_company_service_v2_params_pagination_and_related_endpoints() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/companies"
        ):
            if url.params.get("cursor") == "abc":
                return httpx.Response(
                    200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
                )
            if url.params.get("cursor") is not None:
                raise AssertionError("unexpected cursor value")
            assert url.params.get_list("fieldIds") == ["field-1"]
            assert url.params.get_list("fieldTypes") == ["global"]
            filter_text = url.params.get("filter")
            if filter_text is not None:
                assert filter_text == "x"
            limit = url.params.get("limit")
            if limit is not None:
                assert limit == "1"
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 2, "name": "Acme", "domain": "acme.com"}],
                    "pagination": {"nextUrl": "https://v2.example/v2/companies?cursor=abc"},
                },
                request=request,
            )
        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/companies/2"
        ):
            assert url.params.get_list("fieldIds") == ["field-1"]
            assert url.params.get_list("fieldTypes") == ["global"]
            return httpx.Response(
                200, json={"id": 2, "name": "Acme", "domain": "acme.com"}, request=request
            )
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/list-entries"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "listId": 10, "createdAt": created_at, "fields": {}}],
                    "pagination": {},
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/companies/2/lists"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 10,
                            "name": "L",
                            "type": 0,
                            "public": True,
                            "ownerId": 1,
                            "listSize": 0,
                        }
                    ],
                    "pagination": {},
                },
                request=request,
            )
        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/companies/fields"
        ):
            assert url.params.get_list("fieldTypes") == ["global"]
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "field-1", "name": "F", "valueType": 2, "allowsMultiple": False}
                    ]
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
        svc = CompanyService(http)
        page = svc.list(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x", limit=1)
        assert page.data[0].id == CompanyId(2)
        _ = svc.list(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter=" ")
        assert [
            c.id
            for c in list(
                svc.all(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x")
            )
        ] == [CompanyId(2)]
        assert [
            c.id
            for c in list(
                svc.iter(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x")
            )
        ] == [CompanyId(2)]
        assert (
            svc.get(CompanyId(2), field_ids=["field-1"], field_types=[FieldType.GLOBAL]).name
            == "Acme"
        )
        assert svc.get_list_entries(CompanyId(2)).data[0].list_id == ListId(10)
        assert svc.get_lists(CompanyId(2)).data[0].id == ListId(10)
        assert svc.get_fields(field_types=[FieldType.GLOBAL])[0].id == "field-1"
    finally:
        http.close()


def test_company_service_get_associated_people_v1() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and url == httpx.URL("https://v1.example/organizations/2"):
            return httpx.Response(
                200,
                json={"id": 2, "name": "Acme", "person_ids": [1, 2, 3]},
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/1"):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "primaryEmailAddress": "ada@example.com",
                    "type": 0,
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/2"):
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "firstName": "Alan",
                    "lastName": "Turing",
                    "primaryEmailAddress": "alan@example.com",
                    "type": 1,
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/3"):
            return httpx.Response(
                200,
                json={
                    "id": 3,
                    "firstName": "Grace",
                    "lastName": "Hopper",
                    "primaryEmailAddress": "grace@example.com",
                    "type": 0,
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
        svc = CompanyService(http)
        assert svc.get_associated_person_ids(CompanyId(2)) == [
            PersonId(1),
            PersonId(2),
            PersonId(3),
        ]
        assert svc.get_associated_person_ids(CompanyId(2), max_results=2) == [
            PersonId(1),
            PersonId(2),
        ]
        people = svc.get_associated_people(CompanyId(2), max_results=1)
        assert len(people) == 1
        assert people[0].id == PersonId(1)
        assert people[0].full_name == "Ada Lovelace"
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_company_service_get_associated_people_v1() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and url == httpx.URL("https://v1.example/organizations/2"):
            return httpx.Response(
                200,
                json={"id": 2, "name": "Acme", "person_ids": [1, 2]},
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/1"):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "primaryEmailAddress": "ada@example.com",
                    "type": 0,
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/2"):
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "firstName": "Alan",
                    "lastName": "Turing",
                    "primaryEmailAddress": "alan@example.com",
                    "type": 1,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_beta_endpoints=True,
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    async with client:
        svc = AsyncCompanyService(client)
        assert await svc.get_associated_person_ids(CompanyId(2)) == [
            PersonId(1),
            PersonId(2),
        ]
        people = await svc.get_associated_people(CompanyId(2), max_results=1)
        assert len(people) == 1
        assert people[0].id == PersonId(1)


@pytest.mark.asyncio
async def test_async_person_service_get_supports_field_ids_and_field_types() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/persons/1"
        ):
            assert request.url.params.get_list("fieldIds") == ["field-1"]
            assert request.url.params.get_list("fieldTypes") == ["global"]
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "A",
                    "lastName": "B",
                    "primaryEmailAddress": "a@example.com",
                    "emails": [],
                    "type": "external",
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_beta_endpoints=True,
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = AsyncPersonService(client)
        person = await service.get(
            PersonId(1), field_ids=["field-1"], field_types=[FieldType.GLOBAL]
        )
        assert person.id == PersonId(1)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_person_service_v1_write_search_resolve_merge_and_helpers() -> None:
    calls: dict[str, int] = {"fields": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/persons/fields"
        ):
            assert url.params.get_list("fieldTypes") == ["global"]
            calls["fields"] += 1
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "field-1", "name": "F", "valueType": 2, "allowsMultiple": False}
                    ]
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/persons/1/list-entries"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 10, "listId": 99, "createdAt": "2024-01-01T00:00:00Z"}],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )
        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/persons/1/lists"):
            return httpx.Response(
                200,
                json={"data": [{"id": 99, "name": "People", "type": "person"}], "pagination": {}},
                request=request,
            )
        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            assert request.url.params.get("term") in {"Alice", "alice@example.com"}
            return httpx.Response(
                200,
                json={
                    "persons": [
                        {
                            "id": 1,
                            "firstName": "Alice",
                            "lastName": "Smith",
                            "primaryEmailAddress": "alice@example.com",
                            "emails": ["alice@example.com"],
                            "type": "external",
                        }
                    ],
                    "next_page_token": None,
                },
                request=request,
            )
        if request.method == "POST" and url == httpx.URL("https://v1.example/persons"):
            payload = json.loads(request.content.decode())
            assert payload["first_name"] == "Alice"
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "firstName": "Alice",
                    "lastName": "Smith",
                    "primaryEmailAddress": "alice@example.com",
                    "emails": ["alice@example.com"],
                    "type": "external",
                },
                request=request,
            )
        if request.method == "PUT" and url == httpx.URL("https://v1.example/persons/2"):
            payload = json.loads(request.content.decode())
            assert payload["first_name"] == "Alicia"
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "firstName": "Alicia",
                    "lastName": "Smith",
                    "primaryEmailAddress": "alice@example.com",
                    "emails": ["alice@example.com"],
                    "type": "external",
                },
                request=request,
            )
        if request.method == "DELETE" and url == httpx.URL("https://v1.example/persons/2"):
            return httpx.Response(200, json={"success": True}, request=request)
        if request.method == "POST" and url == httpx.URL("https://v2.example/v2/person-merges"):
            return httpx.Response(200, json={"taskUrl": "tasks/person-merges/abc"}, request=request)
        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/tasks/person-merges/abc"
        ):
            return httpx.Response(200, json={"id": "abc", "status": "success"}, request=request)

        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            enable_beta_endpoints=True,
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = AsyncPersonService(client)
        _ = await service.get_fields(field_types=[FieldType.GLOBAL])
        entries = await service.get_list_entries(PersonId(1))
        assert entries.data[0].id == ListEntryId(10)
        lists = await service.get_lists(PersonId(1))
        assert lists.data[0].id == ListId(99)

        page = await service.search("Alice")
        assert page.data[0].primary_email == "alice@example.com"
        resolved = await service.resolve(email="alice@example.com")
        assert resolved is not None

        created = await service.create(
            PersonCreate(first_name="Alice", last_name="Smith", emails=["alice@example.com"])
        )
        assert created.id == PersonId(2)
        updated = await service.update(PersonId(2), PersonUpdate(first_name="Alicia"))
        assert updated.first_name == "Alicia"
        deleted = await service.delete(PersonId(2))
        assert deleted is True

        task_url = await service.merge(PersonId(1), PersonId(2))
        assert task_url == "tasks/person-merges/abc"
        status = await service.get_merge_status("abc")
        assert status.status == "success"
    finally:
        await client.close()


def test_person_service_resolve_iterates_and_checks_empty_email_lists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            return httpx.Response(
                200,
                json={
                    "persons": [
                        {
                            "id": 1,
                            "firstName": "A",
                            "lastName": "B",
                            "primaryEmailAddress": "a@example.com",
                            "emails": [],
                            "type": "external",
                        },
                        {
                            "id": 2,
                            "firstName": "C",
                            "lastName": "D",
                            "primaryEmailAddress": "c@example.com",
                            "emails": [],
                            "type": "external",
                        },
                    ],
                    "next_page_token": None,
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
        service = PersonService(http)
        assert service.resolve(name="C D") is not None
        assert service.resolve(name="C D").id == PersonId(2)
        assert service.resolve(email="c@example.com") is not None
        assert service.resolve(email="c@example.com").id == PersonId(2)
    finally:
        http.close()


# =============================================================================
# Enhancement 3: include_field_values tests (DX-003)
# =============================================================================


@pytest.mark.req("DX-003")
def test_person_service_get_with_include_field_values() -> None:
    """Test PersonService.get with include_field_values=True uses V1 API."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/1"):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email": "alice@example.com",
                    "emails": ["alice@example.com"],
                    "type": 0,
                    "field_values": [
                        {"id": 10, "field_id": 100, "value": "Active"},
                        {"id": 11, "field_id": 101, "value": "Premium"},
                    ],
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
        service = PersonService(http)
        person = service.get(PersonId(1), include_field_values=True)

        # Verify person data is returned
        assert person.id == PersonId(1)
        assert person.first_name == "Alice"
        assert person.last_name == "Smith"

        # Verify field_values is attached (dynamically added, not in model)
        assert hasattr(person, "field_values")
        field_values = person.field_values  # type: ignore[attr-defined]
        assert len(field_values) == 2
        assert field_values[0]["value"] == "Active"
        assert field_values[1]["value"] == "Premium"
    finally:
        http.close()


@pytest.mark.req("DX-003")
def test_person_service_get_without_include_field_values_uses_v2() -> None:
    """Test PersonService.get without include_field_values uses V2 API."""
    calls: dict[str, int] = {"v1": 0, "v2": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and "/v2/persons/1" in str(url):
            calls["v2"] += 1
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "firstName": "Alice",
                    "lastName": "Smith",
                    "primaryEmailAddress": "alice@example.com",
                    "emails": ["alice@example.com"],
                    "type": "external",
                },
                request=request,
            )
        if request.method == "GET" and str(url).startswith("https://v1.example/persons/"):
            calls["v1"] += 1
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
        service = PersonService(http)

        # Default (include_field_values=False) should use V2
        person = service.get(PersonId(1))
        assert person.id == PersonId(1)
        assert calls["v2"] == 1
        assert calls["v1"] == 0
    finally:
        http.close()


@pytest.mark.asyncio
@pytest.mark.req("DX-003")
async def test_async_person_service_get_with_include_field_values() -> None:
    """Test async PersonService.get with include_field_values=True."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if request.method == "GET" and url == httpx.URL("https://v1.example/persons/1"):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "first_name": "Bob",
                    "last_name": "Jones",
                    "primary_email": "bob@example.com",
                    "emails": ["bob@example.com"],
                    "type": 0,
                    "field_values": [
                        {"id": 20, "field_id": 200, "value": "Manager"},
                    ],
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = AsyncPersonService(client)
        person = await service.get(PersonId(1), include_field_values=True)

        # Verify person data
        assert person.id == PersonId(1)
        assert person.first_name == "Bob"

        # Verify field_values is attached (dynamically added, not in model)
        assert hasattr(person, "field_values")
        field_values = person.field_values  # type: ignore[attr-defined]
        assert len(field_values) == 1
        assert field_values[0]["value"] == "Manager"
    finally:
        await client.close()


# =============================================================================
# TC-004 / TC-005: Tests for search_pages() and search_all() pagination helpers
# =============================================================================


def test_person_service_search_pages_iterates_multiple_pages() -> None:
    """TC-004: Test PersonService.search_pages() pagination."""
    page_tokens = [None, "token1", "token2"]
    current_page = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            current_page[0] += 1
            next_token = (
                page_tokens[current_page[0]] if current_page[0] < len(page_tokens) else None
            )
            return httpx.Response(
                200,
                json={
                    "persons": [
                        {
                            "id": current_page[0],
                            "firstName": f"Person{current_page[0]}",
                            "lastName": "Test",
                            "type": "external",
                        }
                    ],
                    "next_page_token": next_token,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = PersonService(client)
        pages = list(service.search_pages("test"))
        assert len(pages) == 3
        assert pages[0].data[0].first_name == "Person1"
        assert pages[1].data[0].first_name == "Person2"
        assert pages[2].data[0].first_name == "Person3"
    finally:
        client.close()


def test_person_service_search_all_flattens_results() -> None:
    """TC-004: Test PersonService.search_all() auto-pagination."""
    page_tokens = [None, "token1", None]
    current_page = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/persons"
        ):
            current_page[0] += 1
            next_token = (
                page_tokens[current_page[0]] if current_page[0] < len(page_tokens) else None
            )
            return httpx.Response(
                200,
                json={
                    "persons": [
                        {
                            "id": current_page[0],
                            "firstName": f"Person{current_page[0]}",
                            "lastName": "Test",
                            "type": "external",
                        },
                        {
                            "id": current_page[0] + 10,
                            "firstName": f"Person{current_page[0] + 10}",
                            "lastName": "Test",
                            "type": "external",
                        },
                    ],
                    "next_page_token": next_token,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = PersonService(client)
        persons = list(service.search_all("test"))
        assert len(persons) == 4  # 2 per page * 2 pages
        assert persons[0].first_name == "Person1"
        assert persons[1].first_name == "Person11"
        assert persons[2].first_name == "Person2"
        assert persons[3].first_name == "Person12"
    finally:
        client.close()


def test_company_service_search_pages_iterates_multiple_pages() -> None:
    """TC-005: Test CompanyService.search_pages() pagination."""
    page_tokens = [None, "token1", "token2"]
    current_page = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/organizations"
        ):
            current_page[0] += 1
            next_token = (
                page_tokens[current_page[0]] if current_page[0] < len(page_tokens) else None
            )
            return httpx.Response(
                200,
                json={
                    "organizations": [
                        {
                            "id": current_page[0],
                            "name": f"Company{current_page[0]}",
                            "domain": f"company{current_page[0]}.com",
                        }
                    ],
                    "next_page_token": next_token,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = CompanyService(client)
        pages = list(service.search_pages("test"))
        assert len(pages) == 3
        assert pages[0].data[0].name == "Company1"
        assert pages[1].data[0].name == "Company2"
        assert pages[2].data[0].name == "Company3"
    finally:
        client.close()


def test_company_service_search_all_flattens_results() -> None:
    """TC-005: Test CompanyService.search_all() auto-pagination."""
    page_tokens = [None, "token1", None]
    current_page = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.copy_with(query=None) == httpx.URL(
            "https://v1.example/organizations"
        ):
            current_page[0] += 1
            next_token = (
                page_tokens[current_page[0]] if current_page[0] < len(page_tokens) else None
            )
            return httpx.Response(
                200,
                json={
                    "organizations": [
                        {
                            "id": current_page[0],
                            "name": f"Company{current_page[0]}",
                            "domain": f"company{current_page[0]}.com",
                        },
                        {
                            "id": current_page[0] + 10,
                            "name": f"Company{current_page[0] + 10}",
                            "domain": f"company{current_page[0] + 10}.com",
                        },
                    ],
                    "next_page_token": next_token,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        service = CompanyService(client)
        companies = list(service.search_all("test"))
        assert len(companies) == 4  # 2 per page * 2 pages
        assert companies[0].name == "Company1"
        assert companies[1].name == "Company11"
        assert companies[2].name == "Company2"
        assert companies[3].name == "Company12"
    finally:
        client.close()


def test_person_service_get_associated_company_ids() -> None:
    """Test get_associated_company_ids returns CompanyId list from V1 API."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "organization_ids": [100, 200, 300],
                    "type": 0,
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
        svc = PersonService(http)
        company_ids = svc.get_associated_company_ids(PersonId(person_id))
        assert company_ids == [CompanyId(100), CompanyId(200), CompanyId(300)]
    finally:
        http.close()


def test_person_service_get_associated_company_ids_with_max_results() -> None:
    """Test get_associated_company_ids respects max_results."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "organization_ids": [100, 200, 300],
                    "type": 0,
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
        svc = PersonService(http)
        company_ids = svc.get_associated_company_ids(PersonId(person_id), max_results=2)
        assert company_ids == [CompanyId(100), CompanyId(200)]
    finally:
        http.close()


def test_person_service_get_associated_company_ids_empty() -> None:
    """Test get_associated_company_ids returns empty list when no associations."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    # No organization_ids field
                    "type": 0,
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
        svc = PersonService(http)
        company_ids = svc.get_associated_company_ids(PersonId(person_id))
        assert company_ids == []
    finally:
        http.close()


def test_person_service_get_associated_company_ids_camelCase() -> None:
    """Test get_associated_company_ids handles camelCase response keys."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "firstName": "Alice",
                    "lastName": "Smith",
                    "primaryEmailAddress": "alice@example.com",
                    "organizationIds": [100, 200],  # camelCase
                    "type": 0,
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
        svc = PersonService(http)
        company_ids = svc.get_associated_company_ids(PersonId(person_id))
        assert company_ids == [CompanyId(100), CompanyId(200)]
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_person_service_get_associated_company_ids() -> None:
    """Test async get_associated_company_ids returns CompanyId list from V1 API."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "organization_ids": [100, 200, 300],
                    "type": 0,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    async with client:
        svc = AsyncPersonService(client)
        company_ids = await svc.get_associated_company_ids(PersonId(person_id))
        assert company_ids == [CompanyId(100), CompanyId(200), CompanyId(300)]


@pytest.mark.asyncio
async def test_async_person_service_get_associated_company_ids_with_max_results() -> None:
    """Test async get_associated_company_ids respects max_results."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "organization_ids": [100, 200, 300],
                    "type": 0,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    async with client:
        svc = AsyncPersonService(client)
        company_ids = await svc.get_associated_company_ids(PersonId(person_id), max_results=1)
        assert company_ids == [CompanyId(100)]


# =============================================================================
# PersonService.get_associated_opportunity_ids() Tests
# =============================================================================


def test_person_service_get_associated_opportunity_ids() -> None:
    """Test get_associated_opportunity_ids returns OpportunityId list from V1 API."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "opportunity_ids": [500, 600, 700],
                    "type": 0,
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
        svc = PersonService(http)
        opp_ids = svc.get_associated_opportunity_ids(PersonId(person_id))
        assert opp_ids == [OpportunityId(500), OpportunityId(600), OpportunityId(700)]
    finally:
        http.close()


def test_person_service_get_associated_opportunity_ids_with_max_results() -> None:
    """Test get_associated_opportunity_ids respects max_results."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "opportunity_ids": [500, 600, 700],
                    "type": 0,
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
        svc = PersonService(http)
        opp_ids = svc.get_associated_opportunity_ids(PersonId(person_id), max_results=2)
        assert opp_ids == [OpportunityId(500), OpportunityId(600)]
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_person_service_get_associated_opportunity_ids() -> None:
    """Test async get_associated_opportunity_ids returns OpportunityId list."""
    person_id = 123

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/persons/{person_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": person_id,
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "primary_email_address": "alice@example.com",
                    "opportunity_ids": [500, 600],
                    "type": 0,
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    async with client:
        svc = AsyncPersonService(client)
        opp_ids = await svc.get_associated_opportunity_ids(PersonId(person_id))
        assert opp_ids == [OpportunityId(500), OpportunityId(600)]


# =============================================================================
# CompanyService.get_associated_opportunity_ids() Tests
# =============================================================================


def test_company_service_get_associated_opportunity_ids() -> None:
    """Test get_associated_opportunity_ids returns OpportunityId list from V1 API."""
    company_id = 456

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/organizations/{company_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": company_id,
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "opportunity_ids": [800, 900],
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
        svc = CompanyService(http)
        opp_ids = svc.get_associated_opportunity_ids(CompanyId(company_id))
        assert opp_ids == [OpportunityId(800), OpportunityId(900)]
    finally:
        http.close()


def test_company_service_get_associated_opportunity_ids_with_max_results() -> None:
    """Test get_associated_opportunity_ids respects max_results."""
    company_id = 456

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/organizations/{company_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": company_id,
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "opportunity_ids": [800, 900, 1000],
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
        svc = CompanyService(http)
        opp_ids = svc.get_associated_opportunity_ids(CompanyId(company_id), max_results=1)
        assert opp_ids == [OpportunityId(800)]
    finally:
        http.close()


def test_company_service_get_associated_opportunity_ids_empty() -> None:
    """Test get_associated_opportunity_ids returns empty list when no associations."""
    company_id = 456

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/organizations/{company_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": company_id,
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    # No opportunity_ids field
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
        svc = CompanyService(http)
        opp_ids = svc.get_associated_opportunity_ids(CompanyId(company_id))
        assert opp_ids == []
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_company_service_get_associated_opportunity_ids() -> None:
    """Test async get_associated_opportunity_ids returns OpportunityId list."""
    company_id = 456

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and str(request.url) == f"https://v1.example/organizations/{company_id}"
        ):
            return httpx.Response(
                200,
                json={
                    "id": company_id,
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "opportunity_ids": [800, 900],
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
        )
    )
    async with client:
        svc = AsyncCompanyService(client)
        opp_ids = await svc.get_associated_opportunity_ids(CompanyId(company_id))
        assert opp_ids == [OpportunityId(800), OpportunityId(900)]
