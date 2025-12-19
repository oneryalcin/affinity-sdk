from __future__ import annotations

import httpx
import pytest

import affinity.client as affinity_client
from affinity import Affinity, AsyncAffinity
from affinity.policies import Policies, WritePolicy


def test_affinity_from_env_reads_affinity_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AFFINITY_API_KEY", "  secret-key  ")
    client = Affinity.from_env()
    try:
        assert client._http._config.api_key == "secret-key"
    finally:
        client.close()


def test_affinity_from_env_threads_policies_and_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AFFINITY_API_KEY", "secret-key")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}, request=request))
    client = Affinity.from_env(
        policies=Policies(write=WritePolicy.DENY),
        transport=transport,
        max_retries=0,
    )
    try:
        assert client._http._config.policies.write is WritePolicy.DENY
        assert client._http._config.transport is transport
    finally:
        client.close()


def test_affinity_from_env_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AFFINITY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AFFINITY_API_KEY"):
        Affinity.from_env()


def test_affinity_from_env_load_dotenv_requires_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AFFINITY_API_KEY", raising=False)

    original_find_spec = affinity_client.importlib.util.find_spec

    def patched_find_spec(name: str, *args: object, **kwargs: object) -> object | None:
        if name == "dotenv":
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(affinity_client.importlib.util, "find_spec", patched_find_spec)

    with pytest.raises(ImportError, match="python-dotenv"):
        Affinity.from_env(load_dotenv=True)


@pytest.mark.asyncio
async def test_async_affinity_from_env_reads_affinity_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AFFINITY_API_KEY", "async-secret")
    client = AsyncAffinity.from_env()
    try:
        assert client._http._config.api_key == "async-secret"
    finally:
        await client.close()
