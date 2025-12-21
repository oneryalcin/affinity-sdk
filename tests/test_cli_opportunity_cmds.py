from __future__ import annotations

import json

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

try:
    import respx
except ModuleNotFoundError:  # pragma: no cover - optional dev dependency
    respx = None  # type: ignore[assignment]

from click.testing import CliRunner
from httpx import Response

from affinity.cli.main import cli

if respx is None:  # pragma: no cover
    pytest.skip("respx is not installed", allow_module_level=True)


def test_opportunity_ls_minimal(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://api.affinity.co/v2/opportunities").mock(
        return_value=Response(
            200,
            json={
                "data": [{"id": 10, "name": "Seed", "listId": 41780}],
                "pagination": {
                    "nextUrl": "https://api.affinity.co/v2/opportunities?cursor=next",
                    "prevUrl": None,
                },
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "ls"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["opportunities"][0]["id"] == 10
    assert payload["meta"]["pagination"]["opportunities"]["nextCursor"].endswith("cursor=next")


def test_opportunity_get_by_id_minimal(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://api.affinity.co/v2/opportunities/123").mock(
        return_value=Response(200, json={"id": 123, "name": "Series A", "listId": 41780})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "get", "123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["opportunity"]["id"] == 123
    assert payload["meta"]["resolved"]["opportunity"]["source"] == "id"


def test_opportunity_get_accepts_affinity_dot_com_url(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://api.affinity.co/v2/opportunities/123").mock(
        return_value=Response(200, json={"id": 123, "name": "Series A", "listId": 41780})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "get", "https://mydomain.affinity.com/opportunities/123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["meta"]["resolved"]["opportunity"]["source"] == "url"
    assert payload["meta"]["resolved"]["opportunity"]["opportunityId"] == 123


def test_opportunity_get_details_uses_v1(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://api.affinity.co/opportunities/123").mock(
        return_value=Response(
            200,
            json={
                "id": 123,
                "name": "Series A",
                "list_id": 41780,
                "person_ids": [1],
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "get", "123", "--details"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["opportunity"]["listId"] == 41780
    assert payload["data"]["opportunity"]["personIds"] == [1]


def test_opportunity_create_update_delete(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://api.affinity.co/v2/lists/41780").mock(
        return_value=Response(
            200,
            json={
                "id": 41780,
                "name": "Dealflow",
                "type": "opportunity",
                "isPublic": False,
                "ownerId": 1,
                "creatorId": 1,
                "listSize": 0,
            },
        )
    )
    respx_mock.post("https://api.affinity.co/opportunities").mock(
        return_value=Response(
            200,
            json={"id": 123, "name": "Seed", "list_id": 41780},
        )
    )
    respx_mock.put("https://api.affinity.co/opportunities/123").mock(
        return_value=Response(
            200,
            json={"id": 123, "name": "Seed (Updated)", "list_id": 41780},
        )
    )
    respx_mock.delete("https://api.affinity.co/opportunities/123").mock(
        return_value=Response(200, json={"success": True})
    )

    runner = CliRunner()

    created = runner.invoke(
        cli,
        ["--json", "opportunity", "create", "--name", "Seed", "--list", "41780"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert created.exit_code == 0
    created_payload = json.loads(created.output.strip())
    assert created_payload["data"]["opportunity"]["id"] == 123

    updated = runner.invoke(
        cli,
        ["--json", "opportunity", "update", "123", "--name", "Seed (Updated)"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert updated.exit_code == 0
    updated_payload = json.loads(updated.output.strip())
    assert updated_payload["data"]["opportunity"]["name"] == "Seed (Updated)"

    deleted = runner.invoke(
        cli,
        ["--json", "opportunity", "delete", "123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert deleted.exit_code == 0
    deleted_payload = json.loads(deleted.output.strip())
    assert deleted_payload["data"]["success"] is True
