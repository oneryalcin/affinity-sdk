from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from affinity import Affinity, AsyncAffinity
from affinity.clients.http import AsyncHTTPClient, ClientConfig, HTTPClient


def test_affinity_lazy_properties_and_clear_cache() -> None:
    client = Affinity(api_key="k", enable_cache=True, max_retries=0)
    try:
        # Cover lazy-init branches (None -> set) and cached branches (already set)
        _ = client.tasks
        _ = client.tasks
        _ = client.notes
        _ = client.notes
        _ = client.reminders
        _ = client.reminders
        _ = client.webhooks
        _ = client.webhooks
        _ = client.interactions
        _ = client.interactions
        _ = client.fields
        _ = client.fields
        _ = client.field_values
        _ = client.field_values
        _ = client.files
        _ = client.files
        _ = client.relationships
        _ = client.relationships
        _ = client.auth
        _ = client.auth

        assert client._http.cache is not None
        client._http.cache.set("k", {"x": 1})
        client.clear_cache()
        assert client._http.cache.get("k") is None
    finally:
        client.close()


def test_affinity_whoami_convenience_method() -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://v2.example/v2/auth/whoami"):
            return httpx.Response(
                200,
                json={
                    "tenant": {"id": 1, "name": "T", "subdomain": "t"},
                    "user": {"id": 1, "firstName": "A", "lastName": "B", "email": "a@example.com"},
                    "grant": {"type": "api_key", "scope": "all", "createdAt": now},
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = Affinity(api_key="k", max_retries=0)
    try:
        client._http.close()
        client._http = HTTPClient(
            ClientConfig(
                api_key="k",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        client._auth = None
        me = client.whoami()
        assert me.user.email == "a@example.com"
    finally:
        client.close()


def test_affinity_whoami_v2_shape_allows_null_last_name() -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://v2.example/v2/auth/whoami"):
            return httpx.Response(
                200,
                json={
                    "tenant": {"id": 1, "name": "T", "subdomain": "t"},
                    "user": {
                        "id": 1,
                        "firstName": "A",
                        "lastName": None,
                        "emailAddress": "a@example.com",
                    },
                    "grant": {"type": "api-key", "scopes": ["api"], "createdAt": now},
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = Affinity(api_key="k", max_retries=0)
    try:
        client._http.close()
        client._http = HTTPClient(
            ClientConfig(
                api_key="k",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                transport=httpx.MockTransport(handler),
            )
        )
        client._auth = None
        me = client.whoami()
        assert me.user.last_name is None
        assert me.user.email == "a@example.com"
        assert me.grant.scopes == ["api"]
    finally:
        client.close()


def test_affinity_clear_cache_is_noop_when_cache_disabled() -> None:
    client = Affinity(api_key="k", enable_cache=False, max_retries=0)
    try:
        client.clear_cache()
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_affinity_context_manager_and_lazy_properties() -> None:
    async with AsyncAffinity(api_key="k", max_retries=0) as client:
        _ = client.tasks
        _ = client.tasks
        await client.close()

        # close() is idempotent
        await client.close()


@pytest.mark.asyncio
async def test_async_affinity_clear_cache() -> None:
    client = AsyncAffinity(api_key="k", enable_cache=True, max_retries=0)
    try:
        assert client._http.cache is not None
        client._http.cache.set("k", {"x": 1})
        client.clear_cache()
        assert client._http.cache.get("k") is None
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_affinity_clear_cache_is_noop_when_cache_disabled() -> None:
    client = AsyncAffinity(api_key="k", enable_cache=False, max_retries=0)
    try:
        client.clear_cache()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_affinity_whoami_convenience_method() -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://v2.example/v2/auth/whoami"):
            return httpx.Response(
                200,
                json={
                    "tenant": {"id": 1, "name": "T", "subdomain": "t"},
                    "user": {"id": 1, "firstName": "A", "lastName": "B", "email": "a@example.com"},
                    "grant": {"type": "api_key", "scope": "all", "createdAt": now},
                },
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    client = AsyncAffinity(api_key="k", max_retries=0)
    try:
        client._http = AsyncHTTPClient(
            ClientConfig(
                api_key="k",
                v1_base_url="https://v1.example",
                v2_base_url="https://v2.example/v2",
                max_retries=0,
                async_transport=httpx.MockTransport(handler),
            )
        )
        client._auth = None
        me = await client.whoami()
        assert me.user.email == "a@example.com"
    finally:
        await client.close()
