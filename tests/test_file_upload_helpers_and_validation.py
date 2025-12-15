from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.services.v1_only import EntityFileService
from affinity.types import PersonId


def test_entity_files_list_requires_exactly_one_target() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"entity_files": [], "next_page_token": None}, request=request
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
        service = EntityFileService(http)
        with pytest.raises(ValueError, match="Exactly one of person_id"):
            service.list()
        with pytest.raises(ValueError, match="Only one of person_id"):
            service.list(person_id=PersonId(1), organization_id=2)  # type: ignore[arg-type]
    finally:
        http.close()


def test_entity_files_upload_helpers_call_underlying_endpoint_and_progress(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []
    progress: list[tuple[int, int | None, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url == httpx.URL("https://v1.example/entity-files"):
            # Multipart payload; just sanity check the target field is present in the body.
            body = request.content.decode("utf-8", errors="ignore")
            assert "person_id" in body
            seen.append({"content_type": request.headers.get("Content-Type")})
            return httpx.Response(200, json={"success": True}, request=request)
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
        service = EntityFileService(http)

        p = tmp_path / "report.txt"
        p.write_text("hello", encoding="utf-8")

        ok = service.upload_path(
            p,
            person_id=PersonId(1),
            on_progress=lambda done, total, *, phase: progress.append((done, total, phase)),
        )
        assert ok is True
        assert progress[0][0] == 0
        assert progress[0][2] == "upload"
        assert progress[-1][2] == "upload"

        progress.clear()
        ok = service.upload_bytes(
            b"hello",
            "report.txt",
            person_id=PersonId(1),
            on_progress=lambda done, total, *, phase: progress.append((done, total, phase)),
        )
        assert ok is True
        assert progress[0] == (0, 5, "upload")
        assert progress[-1] == (5, 5, "upload")

        assert seen
        assert isinstance(seen[0]["content_type"], str)
        assert "multipart/form-data" in str(seen[0]["content_type"])
    finally:
        http.close()
