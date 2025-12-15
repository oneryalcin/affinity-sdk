from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from affinity.clients.http import ClientConfig, HTTPClient
from affinity.models.entities import FieldCreate, FieldValueCreate
from affinity.models.secondary import (
    InteractionCreate,
    InteractionUpdate,
    NoteCreate,
    NoteUpdate,
    ReminderCreate,
    ReminderUpdate,
    WebhookCreate,
    WebhookUpdate,
)
from affinity.models.types import (
    CompanyId,
    EntityType,
    FieldId,
    FieldValueId,
    FieldValueType,
    FileId,
    InteractionDirection,
    InteractionType,
    ListId,
    NoteId,
    PersonId,
    ReminderIdType,
    ReminderStatus,
    ReminderType,
    UserId,
    WebhookId,
)
from affinity.services.v1_only import (
    AuthService,
    EntityFileService,
    FieldService,
    FieldValueService,
    InteractionService,
    NoteService,
    RelationshipStrengthService,
    ReminderService,
    WebhookService,
)


def test_v1_only_services_end_to_end_smoke_and_branch_coverage(tmp_path: Path) -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    iso = now.isoformat()
    created_at = iso
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        path = url.path

        # Notes
        if request.method == "GET" and path == "/notes":
            return httpx.Response(
                200,
                json={"notes": [{"id": 1, "creatorId": 1, "createdAt": created_at}]},
                request=request,
            )
        if request.method == "GET" and path == "/notes/1":
            return httpx.Response(
                200,
                json={"id": 1, "creatorId": 1, "createdAt": created_at, "content": "x"},
                request=request,
            )
        if request.method == "POST" and path == "/notes":
            seen["note_create"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "creatorId": 1,
                    "createdAt": created_at,
                    "content": "n",
                    "personIds": [1],
                },
                request=request,
            )
        if request.method == "PUT" and path == "/notes/2":
            seen["note_update"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": 2, "creatorId": 1, "createdAt": created_at, "content": "u"},
                request=request,
            )
        if request.method == "DELETE" and path == "/notes/2":
            return httpx.Response(200, json={"success": True}, request=request)

        # Reminders
        if request.method == "GET" and path == "/reminders":
            return httpx.Response(
                200,
                json={
                    "reminders": [
                        {
                            "id": 1,
                            "type": 0,
                            "status": 1,
                            "dueDate": created_at,
                            "createdAt": created_at,
                        }
                    ]
                },
                request=request,
            )
        if request.method == "GET" and path == "/reminders/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "type": 0,
                    "status": 1,
                    "dueDate": created_at,
                    "createdAt": created_at,
                },
                request=request,
            )
        if request.method == "POST" and path == "/reminders":
            seen["reminder_create"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "type": 0,
                    "status": 1,
                    "dueDate": created_at,
                    "createdAt": created_at,
                },
                request=request,
            )
        if request.method == "PUT" and path == "/reminders/2":
            seen["reminder_update"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "type": 0,
                    "status": 1,
                    "dueDate": created_at,
                    "createdAt": created_at,
                },
                request=request,
            )
        if request.method == "DELETE" and path == "/reminders/2":
            return httpx.Response(200, json={"success": True}, request=request)

        # Webhooks
        if request.method == "GET" and path == "/webhook":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": 1, "webhookUrl": "https://x", "createdBy": 1, "subscriptions": []}
                    ]
                },
                request=request,
            )
        if request.method == "GET" and path == "/webhook/1":
            return httpx.Response(
                200,
                json={"id": 1, "webhookUrl": "https://x", "createdBy": 1, "subscriptions": []},
                request=request,
            )
        if request.method == "POST" and path == "/webhook/subscribe":
            seen["webhook_create"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": 2, "webhookUrl": "https://y", "createdBy": 1, "subscriptions": []},
                request=request,
            )
        if request.method == "PUT" and path == "/webhook/2":
            seen["webhook_update"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": 2,
                    "webhookUrl": "https://y",
                    "createdBy": 1,
                    "subscriptions": [],
                    "disabled": True,
                },
                request=request,
            )
        if request.method == "DELETE" and path == "/webhook/2":
            return httpx.Response(200, json={"success": True}, request=request)

        # Interactions
        if request.method == "GET" and path == "/interactions":
            interaction = {"id": 1, "type": 3, "date": created_at}
            if url.params.get("type") == str(int(InteractionType.EMAIL)):
                return httpx.Response(200, json={"emails": [interaction]}, request=request)
            if url.params.get("type") == str(int(InteractionType.MEETING)):
                return httpx.Response(
                    200, json={"events": interaction}, request=request
                )  # not a list -> []
            return httpx.Response(200, json={"interactions": [interaction]}, request=request)
        if request.method == "GET" and path == "/interactions/1":
            return httpx.Response(
                200,
                json={"id": 1, "type": int(InteractionType.EMAIL), "date": created_at},
                request=request,
            )
        if request.method == "POST" and path == "/interactions":
            seen["interaction_create"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": 2, "type": int(InteractionType.EMAIL), "date": created_at},
                request=request,
            )
        if request.method == "PUT" and path == "/interactions/2":
            seen["interaction_update"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": 2, "type": int(InteractionType.EMAIL), "date": created_at},
                request=request,
            )
        if request.method == "DELETE" and path == "/interactions/2":
            return httpx.Response(200, json={"success": True}, request=request)

        # Fields
        if request.method == "GET" and path == "/fields":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "field-1", "name": "F", "valueType": 2, "allowsMultiple": False},
                    ]
                },
                request=request,
            )
        if request.method == "POST" and path == "/fields":
            seen["field_create"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": "field-1", "name": "F", "valueType": 2, "allowsMultiple": True},
                request=request,
            )
        if request.method == "DELETE" and path == "/fields/1":
            return httpx.Response(200, json={"success": True}, request=request)

        # Field values
        if request.method == "GET" and path == "/field-values":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": 1, "fieldId": "field-1", "entityId": 1, "value": "x"},
                    ]
                },
                request=request,
            )
        if request.method == "POST" and path == "/field-values":
            seen["field_value_create"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": 2, "fieldId": "field-1", "entityId": 1, "value": "y"},
                request=request,
            )
        if request.method == "PUT" and path == "/field-values/2":
            seen["field_value_update"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"id": 2, "fieldId": "field-1", "entityId": 1, "value": "z"},
                request=request,
            )
        if request.method == "DELETE" and path == "/field-values/2":
            return httpx.Response(200, json={"success": True}, request=request)

        # Relationship strengths
        if request.method == "GET" and path == "/relationships-strengths":
            return httpx.Response(
                200,
                json={"data": [{"internalId": 2, "externalId": 1, "strength": 0.5}]},
                request=request,
            )

        # Entity files (list/get/upload helpers)
        if request.method == "GET" and path == "/entity-files":
            return httpx.Response(
                200,
                json={
                    "entityFiles": [
                        {
                            "id": 1,
                            "name": "a",
                            "size": 1,
                            "contentType": "x",
                            "uploaderId": 1,
                            "createdAt": created_at,
                        }
                    ]
                },
                request=request,
            )
        if request.method == "GET" and path == "/entity-files/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "a",
                    "size": 1,
                    "contentType": "x",
                    "uploaderId": 1,
                    "createdAt": created_at,
                },
                request=request,
            )
        if request.method == "POST" and path == "/entity-files":
            return httpx.Response(200, json={"success": True}, request=request)

        # Auth
        if request.method == "GET" and path == "/v2/auth/whoami":
            return httpx.Response(
                200,
                json={
                    "tenant": {"id": 1, "name": "T", "subdomain": "s"},
                    "user": {"id": 1, "firstName": "A", "lastName": "B", "email": "a@b"},
                    "grant": {"type": "api_key", "scope": "all", "createdAt": created_at},
                },
                request=request,
            )
        if request.method == "GET" and path == "/rate-limit":
            return httpx.Response(
                200,
                json={
                    "rate": {
                        "orgMonthly": {"limit": 1, "remaining": 1, "reset": 1, "used": 0},
                        "apiKeyPerMinute": {"limit": 1, "remaining": 1, "reset": 1, "used": 0},
                    }
                },
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
        http.cache.set("field_meta", {"x": 1})
        http.cache.set("list_10_fields", {"x": 1})
        http.cache.set("person_fields:global", {"x": 1})
        http.cache.set("company_fields:global", {"x": 1})

        notes = NoteService(http)
        assert notes.list(person_id=PersonId(1)).data[0].id == NoteId(1)
        assert notes.get(NoteId(1)).content == "x"
        created = notes.create(
            NoteCreate(
                content="n",
                person_ids=[PersonId(1)],
                creator_id=UserId(1),
                created_at=now,
            )
        )
        assert created.id == NoteId(2)
        updated = notes.update(NoteId(2), NoteUpdate(content="u"))
        assert updated.content == "u"
        assert notes.delete(NoteId(2)) is True
        assert seen["note_create"]["created_at"] == iso
        assert seen["note_update"] == {"content": "u"}

        reminders = ReminderService(http)
        assert reminders.list(person_id=PersonId(1), status=ReminderStatus.ACTIVE).data[
            0
        ].id == ReminderIdType(1)
        assert reminders.get(ReminderIdType(1)).status == ReminderStatus.ACTIVE
        created_r = reminders.create(
            ReminderCreate(
                owner_id=UserId(1),
                type=ReminderType.ONE_TIME,
                content="c",
                due_date=now,
                person_id=PersonId(1),
            )
        )
        assert created_r.id == ReminderIdType(2)
        _ = reminders.update(
            ReminderIdType(2), ReminderUpdate(owner_id=UserId(2), is_completed=True)
        )
        assert reminders.delete(ReminderIdType(2)) is True
        assert seen["reminder_create"]["owner_id"] == 1
        assert seen["reminder_update"]["is_completed"] is True

        webhooks = WebhookService(http)
        assert webhooks.list()[0].id == WebhookId(1)
        assert webhooks.get(WebhookId(1)).webhook_url == "https://x"
        created_w = webhooks.create(WebhookCreate(webhook_url="https://y"))
        assert created_w.id == WebhookId(2)
        _ = webhooks.update(WebhookId(2), WebhookUpdate(disabled=True))
        assert webhooks.delete(WebhookId(2)) is True
        assert seen["webhook_create"] == {"webhook_url": "https://y"}
        assert seen["webhook_update"]["disabled"] is True

        interactions = InteractionService(http)
        assert interactions.list(type=InteractionType.EMAIL).data[0].id == 1
        assert interactions.list(type=InteractionType.MEETING).data == []
        assert interactions.list().data[0].id == 1
        assert interactions.get(1, InteractionType.EMAIL).id == 1
        created_i = interactions.create(
            InteractionCreate(
                type=InteractionType.EMAIL,
                person_ids=[PersonId(1)],
                content="c",
                date=now,
                direction=InteractionDirection.OUTGOING,
            )
        )
        assert created_i.id == 2
        updated_i = interactions.update(
            2,
            InteractionType.EMAIL,
            InteractionUpdate(content="u", direction=InteractionDirection.INCOMING),
        )
        assert updated_i.id == 2
        assert interactions.delete(2, InteractionType.EMAIL) is True
        assert seen["interaction_create"]["direction"] == int(InteractionDirection.OUTGOING)
        assert seen["interaction_update"]["direction"] == int(InteractionDirection.INCOMING)

        fields = FieldService(http)
        assert fields.list(list_id=ListId(10), entity_type=EntityType.PERSON)[0].id == FieldId(
            "field-1"
        )
        created_f = fields.create(
            FieldCreate(
                name="F",
                entity_type=EntityType.PERSON,
                value_type=FieldValueType.TEXT,
                list_id=ListId(10),
                allows_multiple=True,
                is_list_specific=True,
                is_required=True,
            )
        )
        assert created_f.id == FieldId("field-1")
        assert http.cache.get("field_meta") is None
        assert http.cache.get("list_10_fields") is None
        assert fields.delete(FieldId("field-1")) is True
        assert seen["field_create"]["is_list_specific"] is True

        field_values = FieldValueService(http)
        with pytest.raises(ValueError):
            field_values.list()
        with pytest.raises(ValueError):
            field_values.list(person_id=PersonId(1), organization_id=CompanyId(2))
        assert field_values.list(person_id=PersonId(1))[0].id == 1
        created_v = field_values.create(FieldValueCreate(field_id="1", entity_id=1, value="y"))
        assert created_v.id == 2
        _ = field_values.update(FieldValueId(2), "z")
        assert field_values.delete(FieldValueId(2)) is True
        assert seen["field_value_create"]["field_id"] == 1

        rel = RelationshipStrengthService(http)
        strengths = rel.get(PersonId(1), internal_id=UserId(2))
        assert strengths[0].strength == 0.5

        files = EntityFileService(http)
        with pytest.raises(ValueError):
            files.list()
        with pytest.raises(ValueError):
            files.list(person_id=PersonId(1), organization_id=CompanyId(2))
        assert files.list(person_id=PersonId(1)).data[0].id == FileId(1)
        assert files.get(FileId(1)).name == "a"
        assert files.upload_bytes(b"x", "a.txt", person_id=PersonId(1)) is True
        p = tmp_path / "a.txt"
        p.write_text("x", encoding="utf-8")
        assert files.upload_path(p, person_id=PersonId(1)) is True

        auth = AuthService(http)
        assert auth.whoami().tenant.name == "T"
        assert auth.get_rate_limits().org_monthly.limit == 1
    finally:
        http.close()
