from __future__ import annotations

import pytest

from affinity import Affinity, AsyncAffinity


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
