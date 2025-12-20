from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from affinity.clients.http import AsyncHTTPClient, ClientConfig
from affinity.exceptions import TimeoutError
from affinity.services.v1_only import AsyncEntityFileService
from affinity.types import FileId


@pytest.mark.asyncio
async def test_async_entity_file_download_stream_forwards_timeout_to_httpx_stream() -> None:
    seen_timeouts: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            return httpx.Response(
                302,
                headers={"Location": "https://files.example/content.bin"},
                request=request,
            )
        if request.method == "GET" and request.url == httpx.URL(
            "https://files.example/content.bin"
        ):
            return httpx.Response(200, content=b"ok", request=request)
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
        async_client = await http._get_client()
        orig_stream = async_client.stream

        def stream_wrapper(method: str, url: str, **kwargs: object) -> object:
            seen_timeouts.append(kwargs.get("timeout"))
            return orig_stream(method, url, **kwargs)

        async_client.stream = stream_wrapper  # type: ignore[method-assign]

        files = AsyncEntityFileService(http)
        chunks: list[bytes] = []
        async for chunk in files.download_stream(FileId(5), timeout=1.23):
            chunks.append(chunk)
        assert b"".join(chunks) == b"ok"
        assert 1.23 in seen_timeouts
    finally:
        await http.close()


@pytest.mark.asyncio
async def test_async_entity_file_download_stream_with_info_exposes_filename_and_size() -> None:
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
                content=b"hello",
                headers={
                    "Content-Length": "5",
                    "Content-Disposition": 'attachment; filename="report.pdf"',
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
        files = AsyncEntityFileService(http)
        downloaded = await files.download_stream_with_info(FileId(5), chunk_size=2)
        assert downloaded.filename == "report.pdf"
        assert downloaded.size == 5
        chunks: list[bytes] = []
        async for chunk in downloaded.iter_bytes:
            chunks.append(chunk)
        assert b"".join(chunks) == b"hello"
    finally:
        await http.close()


@pytest.mark.asyncio
async def test_async_entity_file_download_stream_deadline_seconds_enforced(
    monkeypatch: Any,
) -> None:
    t = {"now": 0.0}
    monkeypatch.setattr("affinity.clients.http.time.monotonic", lambda: t["now"])

    class TwoChunkStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"a"
            t["now"] = 1.0
            yield b"b"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            return httpx.Response(
                302,
                headers={"Location": "https://files.example/content.bin"},
                request=request,
            )
        if request.method == "GET" and request.url == httpx.URL(
            "https://files.example/content.bin"
        ):
            return httpx.Response(
                200,
                stream=TwoChunkStream(),
                headers={"Content-Length": "2"},
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
        files = AsyncEntityFileService(http)
        it = files.download_stream(FileId(5), chunk_size=1, deadline_seconds=0.1)
        assert await anext(it) == b"a"
        with pytest.raises(TimeoutError):
            await anext(it)
    finally:
        await http.close()
