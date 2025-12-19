from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest

from affinity.clients.http import AsyncHTTPClient, ClientConfig, HTTPClient
from affinity.exceptions import ConfigurationError, UnsafeUrlError
from affinity.hooks import HookEvent
from affinity.policies import ExternalHookPolicy, Policies


def test_sync_stream_download_emits_redirect_and_stream_events_in_order_with_redaction() -> None:
    events: list[HookEvent] = []

    def on_event(event: HookEvent) -> None:
        events.append(event)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            return httpx.Response(
                302,
                headers={"Location": "https://files.example/content.bin?token=secret"},
                request=request,
            )
        if request.method == "GET" and request.url == httpx.URL(
            "https://files.example/content.bin?token=secret"
        ):
            return httpx.Response(
                200,
                content=b"hello-world",
                headers={"Content-Length": "11"},
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
            on_event=on_event,
        )
    )
    try:
        assert (
            b"".join(http.stream_download("/entity-files/download/5", v1=True, chunk_size=3))
            == b"hello-world"
        )
    finally:
        http.close()

    event_types = [e.type for e in events]
    assert event_types[:4] == [
        "request_started",
        "redirect_followed",
        "response_headers_received",
        "stream_completed",
    ]

    redirect = events[1]
    assert redirect.type == "redirect_followed"
    assert redirect.to_url == "https://files.example/content.bin"

    headers_received = events[2]
    assert headers_received.type == "response_headers_received"
    assert headers_received.status_code == 200
    assert headers_received.external is True

    completed = events[3]
    assert completed.type == "stream_completed"
    assert completed.bytes_read == 11
    assert completed.external is True


def test_external_hook_policy_suppress_drops_external_events() -> None:
    events: list[str] = []

    def on_event(event: HookEvent) -> None:
        events.append(event.type)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            return httpx.Response(
                302,
                headers={"Location": "https://files.example/content.bin?token=secret"},
                request=request,
            )
        if request.method == "GET" and request.url == httpx.URL(
            "https://files.example/content.bin?token=secret"
        ):
            return httpx.Response(200, content=b"ok", request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
            on_event=on_event,
            policies=Policies(external_hooks=ExternalHookPolicy.SUPPRESS),
        )
    )
    try:
        assert b"".join(http.stream_download("/entity-files/download/5", v1=True)) == b"ok"
    finally:
        http.close()

    assert events == ["request_started"]


def test_hook_error_policy_swallow_does_not_break_requests() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True}, request=request)

    def on_event(_event: HookEvent) -> None:
        raise RuntimeError("hook exploded")

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
            on_event=on_event,
            hook_error_policy="swallow",
        )
    )
    try:
        assert http.get("/auth/whoami") == {"ok": True}
        assert calls == ["https://v2.example/v2/auth/whoami"]
    finally:
        http.close()


def test_hook_error_policy_raise_propagates_hook_exceptions_and_prevents_network_call() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"ok": True}, request=request)

    def on_event(_event: HookEvent) -> None:
        raise RuntimeError("hook exploded")

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
            on_event=on_event,
            hook_error_policy="raise",
        )
    )
    try:
        with pytest.raises(RuntimeError, match="hook exploded"):
            _ = http.get("/auth/whoami")
        assert calls == []
    finally:
        http.close()


def test_sync_on_event_returning_awaitable_raises_configuration_error_when_policy_is_raise() -> (
    None
):
    async def on_event(_event: HookEvent) -> None:
        return None

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"ok": True}, request=r)
            ),
            on_event=on_event,  # type: ignore[arg-type]
            hook_error_policy="raise",
        )
    )
    try:
        with pytest.raises(ConfigurationError, match="synchronous `on_event`"):
            _ = http.get("/auth/whoami")
    finally:
        http.close()


def test_download_redirect_cap_is_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        parts = urlsplit(str(request.url))
        hop = 0
        if parts.query.startswith("hop="):
            hop = int(parts.query.split("=", 1)[1])
        return httpx.Response(
            302,
            headers={"Location": f"/entity-files/download/5?hop={hop + 1}"},
            request=request,
        )

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
        with pytest.raises(UnsafeUrlError, match="too many redirects"):
            _ = http.download_file("/entity-files/download/5?hop=0", v1=True)
    finally:
        http.close()


def test_blocked_insecure_redirect_emits_request_failed_event() -> None:
    events: list[HookEvent] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            return httpx.Response(
                302,
                headers={"Location": "http://files.example/x"},
                request=request,
            )
        return httpx.Response(200, content=b"x", request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
            on_event=events.append,
        )
    )
    try:
        with pytest.raises(UnsafeUrlError):
            _ = http.download_file("/entity-files/download/5", v1=True)
    finally:
        http.close()

    assert [e.type for e in events] == ["request_started", "request_failed"]
    failed = events[1]
    assert failed.type == "request_failed"
    assert isinstance(failed.error, UnsafeUrlError)


@pytest.mark.asyncio
async def test_async_concurrent_downloads_have_distinct_client_request_ids() -> None:
    seen_ids_by_path: dict[str, str] = {}
    lock = asyncio.Lock()
    events: list[HookEvent] = []

    def on_event(event: HookEvent) -> None:
        events.append(event)

    async def handler(request: httpx.Request) -> httpx.Response:
        client_request_id = request.headers.get("X-Client-Request-Id")
        assert client_request_id is not None
        async with lock:
            seen_ids_by_path[request.url.path] = client_request_id
        return httpx.Response(200, content=b"file", request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
            on_event=on_event,
        )
    )
    try:
        a, b = await asyncio.gather(
            http.download_file("/entity-files/download/1", v1=True),
            http.download_file("/entity-files/download/2", v1=True),
        )
        assert a == b"file"
        assert b == b"file"
    finally:
        await http.close()

    assert (
        seen_ids_by_path["/entity-files/download/1"] != seen_ids_by_path["/entity-files/download/2"]
    )

    started = [e for e in events if e.type == "request_started"]
    succeeded = [e for e in events if e.type == "request_succeeded"]
    assert len(started) == 2
    assert len(succeeded) == 2

    seen_event_ids = {e.client_request_id for e in started}
    assert seen_event_ids == set(seen_ids_by_path.values())


@pytest.mark.asyncio
async def test_async_stream_download_emits_stream_aborted_even_when_no_bytes_read() -> None:
    events: list[HookEvent] = []

    class CancelStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            raise asyncio.CancelledError()
            yield b""  # pragma: no cover

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            return httpx.Response(
                302,
                headers={"Location": "https://files.example/content.bin?token=secret"},
                request=request,
            )
        if request.method == "GET" and request.url == httpx.URL(
            "https://files.example/content.bin?token=secret"
        ):
            return httpx.Response(200, stream=CancelStream(), request=request)
        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = AsyncHTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            async_transport=httpx.MockTransport(handler),
            on_event=events.append,
        )
    )
    try:
        it = http.stream_download("/entity-files/download/5", v1=True)
        with pytest.raises(asyncio.CancelledError):
            await anext(it)
    finally:
        await http.close()

    assert "stream_aborted" in [e.type for e in events]
    aborted = next(e for e in events if e.type == "stream_aborted")
    assert aborted.bytes_read == 0
