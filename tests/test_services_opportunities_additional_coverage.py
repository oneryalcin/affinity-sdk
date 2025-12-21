from __future__ import annotations

import httpx

from affinity.client import ClientConfig
from affinity.clients.http import AsyncHTTPClient, HTTPClient
from affinity.models.types import ListId, OpportunityId
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
