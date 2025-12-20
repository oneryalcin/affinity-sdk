from __future__ import annotations

from base64 import b64encode
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.exceptions import TimeoutError
from affinity.services.v1_only import EntityFileService
from affinity.types import FileId


def test_entity_file_download_stream_follows_redirect_without_leaking_basic_auth() -> None:
    seen: list[httpx.Request] = []
    progress: list[tuple[int, int | None, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)

        if request.method == "GET" and request.url == httpx.URL(
            "https://v1.example/entity-files/download/5"
        ):
            expected = "Basic " + b64encode(b":k").decode("ascii")
            assert request.headers.get("Authorization") == expected
            return httpx.Response(
                302,
                headers={"Location": "https://files.example/content.bin?token=secret"},
                request=request,
            )

        if request.method == "GET" and request.url == httpx.URL(
            "https://files.example/content.bin?token=secret"
        ):
            assert "Authorization" not in request.headers
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
            v1_auth_mode="basic",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        files = EntityFileService(http)
        chunks = list(
            files.download_stream(
                FileId(5),
                chunk_size=4,
                on_progress=lambda done, total, *, phase: progress.append((done, total, phase)),
            )
        )
        assert b"".join(chunks) == b"hello-world"
        assert chunks == [b"hell", b"o-wo", b"rld"]
        assert progress[0] == (0, 11, "download")
        assert progress[-1] == (11, 11, "download")
    finally:
        http.close()


def test_entity_file_download_retries_on_transient_external_failure() -> None:
    external_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal external_calls

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
            external_calls += 1
            if external_calls == 1:
                return httpx.Response(500, content=b"temporary", request=request)
            return httpx.Response(200, content=b"ok", request=request)

        return httpx.Response(404, json={"message": "not found"}, request=request)

    http = HTTPClient(
        ClientConfig(
            api_key="k",
            v1_base_url="https://v1.example",
            v2_base_url="https://v2.example/v2",
            max_retries=1,
            retry_delay=0.0,
            transport=httpx.MockTransport(handler),
        )
    )
    try:
        files = EntityFileService(http)
        content = files.download(FileId(5))
        assert content == b"ok"
        assert external_calls == 2
    finally:
        http.close()


def test_entity_file_download_to_writes_path(tmp_path: Path) -> None:
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
            return httpx.Response(200, content=b"abc", request=request)
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
        files = EntityFileService(http)
        dest = tmp_path / "out.bin"
        written = files.download_to(FileId(5), dest)
        assert written == dest
        assert dest.read_bytes() == b"abc"

        with pytest.raises(FileExistsError):
            files.download_to(FileId(5), dest, overwrite=False)

        files.download_to(FileId(5), dest, overwrite=True)
        assert dest.read_bytes() == b"abc"
    finally:
        http.close()


def test_entity_file_download_stream_forwards_timeout_to_httpx_stream() -> None:
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
        orig_stream = http._client.stream

        def stream_wrapper(method: str, url: str, **kwargs: object) -> object:
            seen_timeouts.append(kwargs.get("timeout"))
            return orig_stream(method, url, **kwargs)

        http._client.stream = stream_wrapper  # type: ignore[method-assign]

        files = EntityFileService(http)
        assert b"".join(files.download_stream(FileId(5), timeout=1.23)) == b"ok"
        assert 1.23 in seen_timeouts
    finally:
        http.close()


def test_entity_file_download_stream_with_info_exposes_headers_filename_and_size() -> None:
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
                    "Content-Type": "application/octet-stream",
                    "Content-Disposition": 'attachment; filename="report.pdf"',
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
        files = EntityFileService(http)
        downloaded = files.download_stream_with_info(FileId(5), chunk_size=2)
        assert downloaded.filename == "report.pdf"
        assert downloaded.size == 5
        assert downloaded.content_type == "application/octet-stream"
        assert b"".join(downloaded.iter_bytes) == b"hello"
    finally:
        http.close()


def test_entity_file_download_stream_with_info_parses_rfc5987_filename_star() -> None:
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
                content=b"ok",
                headers={
                    "Content-Disposition": "attachment; filename*=UTF-8''hello%20world.txt",
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
        files = EntityFileService(http)
        downloaded = files.download_stream_with_info(FileId(5))
        assert downloaded.filename == "hello world.txt"
        assert b"".join(downloaded.iter_bytes) == b"ok"
    finally:
        http.close()


def test_entity_file_download_stream_deadline_seconds_enforced(monkeypatch: Any) -> None:
    t = {"now": 0.0}
    monkeypatch.setattr("affinity.clients.http.time.monotonic", lambda: t["now"])

    class TwoChunkStream(httpx.SyncByteStream):
        def __init__(self, request: httpx.Request):
            self._request = request

        def __iter__(self) -> Iterator[bytes]:
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
                stream=TwoChunkStream(request),
                headers={"Content-Length": "2"},
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
        files = EntityFileService(http)
        it = files.download_stream(FileId(5), chunk_size=1, deadline_seconds=0.1)
        assert next(it) == b"a"
        with pytest.raises(TimeoutError):
            next(it)
    finally:
        http.close()
