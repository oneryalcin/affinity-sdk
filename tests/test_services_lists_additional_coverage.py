from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from affinity.clients.http import AsyncHTTPClient, ClientConfig, HTTPClient
from affinity.models.entities import ListCreate, ListPermission
from affinity.models.types import (
    FieldType,
    ListEntryId,
    ListId,
    ListRole,
    ListType,
    PersonId,
    UserId,
)
from affinity.services.lists import AsyncListEntryService, AsyncListService, ListService


def test_list_service_list_all_get_fields_and_create_entry_helpers() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
    calls: dict[str, int] = {"fields": 0, "lists": 0}
    person_entries_calls = 0
    field_values_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/lists"
        ):
            if url.params.get("cursor") is not None:
                return httpx.Response(
                    200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
                )
            calls["lists"] += 1
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
                            "creatorId": 1,
                            "listSize": 1,
                        }
                    ],
                    "pagination": {"nextUrl": "https://v2.example/v2/lists?cursor=abc"},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/lists?cursor=abc"):
            return httpx.Response(
                200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/lists/10"):
            return httpx.Response(
                200,
                json={
                    "id": 10,
                    "name": "L",
                    "type": 0,
                    "public": True,
                    "ownerId": 1,
                    "creatorId": 1,
                    "listSize": 1,
                    "fields": [],
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/lists/10/fields"
        ):
            calls["fields"] += 1
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "field-1", "name": "F", "valueType": 2, "allowsMultiple": False},
                    ]
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries"
        ):
            if url.params.get("cursor") is not None:
                return httpx.Response(
                    200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
                )
            filter_text = url.params.get("filter")
            assert filter_text is None
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "listId": 10,
                            "createdAt": created_at,
                            "type": "person",
                            "entity": {"id": 1, "type": "external"},
                            "fields": {},
                        }
                    ],
                    "pagination": {
                        "nextUrl": "https://v2.example/v2/lists/10/list-entries?cursor=abc"
                    },
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries?cursor=abc"
        ):
            return httpx.Response(
                200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries/1"
        ):
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "listId": 10,
                    "createdAt": created_at,
                    "type": "person",
                    "entity": {"id": 1, "type": "external"},
                    "fields": {},
                },
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/lists/10/saved-views/1/list-entries"
        ):
            limit = url.params.get("limit")
            if limit is not None:
                assert limit == "1"
            return httpx.Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/persons/1/list-entries"
        ):
            nonlocal person_entries_calls
            person_entries_calls += 1
            if person_entries_calls == 1:
                return httpx.Response(
                    200,
                    json={
                        "data": [{"id": 5, "listId": 999, "createdAt": created_at, "fields": {}}],
                        "pagination": {"nextUrl": None},
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 5, "listId": 10, "createdAt": created_at, "fields": {}}],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        if request.method == "POST" and url == httpx.URL(
            "https://v1.example/lists/10/list-entries"
        ):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload in ({"entity_id": 1}, {"entity_id": 1, "creator_id": 123})
            return httpx.Response(
                200,
                json={"id": 5, "listId": 10, "createdAt": created_at, "entityId": 1, "fields": {}},
                request=request,
            )

        if request.method == "DELETE" and url == httpx.URL(
            "https://v1.example/lists/10/list-entries/5"
        ):
            return httpx.Response(200, json={"success": True}, request=request)

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries/5/fields"
        ):
            nonlocal field_values_calls
            field_values_calls += 1
            if field_values_calls == 1:
                return httpx.Response(200, json={"data": {}}, request=request)
            return httpx.Response(200, json={"data": []}, request=request)

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries/5/fields/field-1"
        ):
            return httpx.Response(200, json={"value": "x"}, request=request)

        if request.method == "POST" and url == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries/5/fields/field-1"
        ):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"value": "y"}
            return httpx.Response(200, json={"field-1": "y"}, request=request)

        if request.method == "PATCH" and url == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries/5/fields"
        ):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {"operations": [{"fieldId": "field-1", "value": "y"}]}
            return httpx.Response(
                200, json={"results": [{"fieldId": "field-1", "success": True}]}, request=request
            )

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
        svc = ListService(http)
        page = svc.list()
        assert page.data[0].type == ListType.PERSON
        assert [lst.id for lst in list(svc.all())] == [ListId(10)]
        assert svc.get(ListId(10)).id == ListId(10)

        _ = svc.get_fields(ListId(10), field_types=[FieldType.GLOBAL])
        _ = svc.get_fields(ListId(10), field_types=[FieldType.GLOBAL])
        assert calls["fields"] == 1

        entries = svc.entries(ListId(10))
        _ = entries.list(filter="  ")
        assert [e.id for e in list(entries.all())] == [ListEntryId(1)]
        assert entries.get(ListEntryId(1)).id == ListEntryId(1)
        assert entries.from_saved_view(1).data == []
        assert entries.from_saved_view(1, limit=1).data == []

        ensured = entries.ensure_person(PersonId(1))
        assert ensured.id == ListEntryId(5)
        ensured_with_creator = entries.ensure_person(PersonId(1), creator_id=123)
        assert ensured_with_creator.id == ListEntryId(5)
        assert entries.find_person(PersonId(1)) is not None

        assert entries.delete(ListEntryId(5)) is True

        assert entries.get_field_values(ListEntryId(5)).requested is True
        assert entries.get_field_values(ListEntryId(5)).requested is True
        assert entries.get_field_value(ListEntryId(5), "field-1") == "x"
        assert entries.update_field_value(ListEntryId(5), "field-1", "y").requested is True
        assert entries.batch_update_fields(ListEntryId(5), {"field-1": "y"}).all_successful is True
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_list_service_and_list_entry_membership() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/lists"):
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
                            "listSize": 1,
                        }
                    ],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/lists/10"):
            return httpx.Response(
                200,
                json={
                    "id": 10,
                    "name": "L",
                    "type": 0,
                    "public": True,
                    "ownerId": 1,
                    "listSize": 1,
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

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/list-entries"
        ):
            return httpx.Response(
                200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
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
        lists = AsyncListService(client)
        assert (await lists.list()).data[0].id == ListId(10)
        assert (await lists.get(ListId(10))).name == "L"

        entries = AsyncListEntryService(client, ListId(10))
        assert await entries.find_person(PersonId(1)) is not None
        assert await entries.find_company(2) is None
    finally:
        await client.close()


def test_list_service_create_saved_views_and_list_entry_params() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
    invalidated_prefixes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "POST" and url == httpx.URL("https://v1.example/lists"):
            payload = json.loads(request.content.decode("utf-8"))
            assert payload == {
                "name": "New List",
                "type": 0,
                "is_public": True,
                "owner_id": 1,
                "additional_permissions": [{"internal_person_id": 2, "role_id": 1}],
            }
            return httpx.Response(
                200,
                json={
                    "id": 11,
                    "name": "New List",
                    "type": 0,
                    "public": True,
                    "ownerId": 1,
                    "creatorId": 1,
                    "listSize": 0,
                    "fields": [],
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/lists/11/saved-views"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 1, "name": "SV", "listId": 11, "fieldIds": []}],
                    "pagination": {},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/lists/11/saved-views/1"
        ):
            return httpx.Response(
                200,
                json={"id": 1, "name": "SV", "listId": 11, "fieldIds": []},
                request=request,
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/lists/11/list-entries"
        ):
            assert url.params.get_list("fieldIds") == ["field-1"]
            assert url.params.get_list("fieldTypes") == ["global"]
            assert url.params.get("filter") == "x"
            limit = url.params.get("limit")
            if limit is not None:
                assert limit == "1"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "listId": 11,
                            "createdAt": created_at,
                            "type": "person",
                            "entity": {"id": 1, "type": "external"},
                            "fields": {},
                        }
                    ],
                    "pagination": {"nextUrl": None},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/companies/2/list-entries"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 2, "listId": 11, "createdAt": created_at, "fields": {}}],
                    "pagination": {},
                },
                request=request,
            )

        if request.method == "POST" and url == httpx.URL(
            "https://v1.example/lists/11/list-entries"
        ):
            return httpx.Response(
                200,
                json={"id": 99, "listId": 11, "createdAt": created_at, "entityId": 3, "fields": {}},
                request=request,
            )

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
        assert http.cache is not None

        original_invalidate = http.cache.invalidate_prefix

        def recording_invalidate(prefix: str) -> None:
            invalidated_prefixes.append(prefix)
            original_invalidate(prefix)

        http.cache.invalidate_prefix = recording_invalidate  # type: ignore[method-assign]

        svc = ListService(http)
        created = svc.create(
            ListCreate(
                name="New List",
                type=ListType.PERSON,
                is_public=True,
                owner_id=UserId(1),
                additional_permissions=[
                    ListPermission(internal_person_id=UserId(2), role_id=ListRole.BASIC)
                ],
            )
        )
        assert created.id == ListId(11)
        assert invalidated_prefixes == ["list"]

        saved = svc.get_saved_views(ListId(11))
        assert saved.data[0].id == 1
        assert svc.get_saved_view(ListId(11), 1).name == "SV"

        entries = svc.entries(ListId(11))
        _ = entries.list(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x", limit=1)
        assert [
            e.id
            for e in list(
                entries.iter(field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x")
            )
        ] == [ListEntryId(1)]
        existing = entries.ensure_company(2)
        assert existing.id == ListEntryId(2)

        created_entry = entries.add_opportunity(3)
        assert created_entry.id == ListEntryId(99)
    finally:
        http.close()


def test_list_create_does_not_invalidate_when_cache_disabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url == httpx.URL("https://v1.example/lists"):
            return httpx.Response(
                200,
                json={
                    "id": 12,
                    "name": "X",
                    "type": 0,
                    "public": True,
                    "ownerId": 1,
                    "listSize": 0,
                },
                request=request,
            )
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
        svc = ListService(http)
        created = svc.create(ListCreate(name="X", type=ListType.PERSON, is_public=True))
        assert created.id == ListId(12)
    finally:
        http.close()


@pytest.mark.asyncio
async def test_async_list_service_and_entry_list_all_iter_with_pagination() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/lists"):
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
                            "listSize": 1,
                        }
                    ],
                    "pagination": {"nextUrl": "https://v2.example/v2/lists?cursor=abc"},
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL("https://v2.example/v2/lists?cursor=abc"):
            return httpx.Response(
                200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
            )

        if request.method == "GET" and url.copy_with(query=None) == httpx.URL(
            "https://v2.example/v2/lists/10/list-entries"
        ):
            if url.params.get("cursor") == "xyz":
                return httpx.Response(
                    200, json={"data": [], "pagination": {"nextUrl": None}}, request=request
                )
            if url.params.get("cursor") is not None:
                raise AssertionError("unexpected cursor value")
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
                            "listId": 10,
                            "createdAt": created_at,
                            "type": "person",
                            "entity": {"id": 1, "type": "external"},
                            "fields": {},
                        }
                    ],
                    "pagination": {
                        "nextUrl": "https://v2.example/v2/lists/10/list-entries?cursor=xyz"
                    },
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/persons/1/list-entries"
        ):
            return httpx.Response(
                200,
                json={
                    "data": [{"id": 2, "listId": 10, "createdAt": created_at, "fields": {}}],
                    "pagination": {
                        "nextUrl": "https://v2.example/v2/persons/1/list-entries?cursor=abc"
                    },
                },
                request=request,
            )

        if request.method == "GET" and url == httpx.URL(
            "https://v2.example/v2/persons/1/list-entries?cursor=abc"
        ):
            return httpx.Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
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
        lists = AsyncListService(client)
        assert [lst.id async for lst in lists.all()] == [ListId(10)]

        entries = AsyncListEntryService(client, ListId(10))
        _ = await entries.list(
            field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter=" ", limit=1
        )
        _ = await entries.list(
            field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter="x", limit=1
        )
        _ = await entries.list()
        assert [
            e.id
            async for e in entries.all(
                field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter=" "
            )
        ] == [ListEntryId(1)]
        assert [
            e.id
            async for e in entries.iter(
                field_ids=["field-1"], field_types=[FieldType.GLOBAL], filter=" "
            )
        ] == [ListEntryId(1)]
        assert (await entries.find_person(PersonId(1))) is not None
    finally:
        await client.close()
