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
from affinity.models.types import CompanyId, FieldType, ListId, ListType, PersonId, PersonType
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
                organization_ids=[CompanyId(2)],
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
                organization_ids=[CompanyId(2)],
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
