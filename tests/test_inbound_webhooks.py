from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from affinity.exceptions import (
    WebhookInvalidJsonError,
    WebhookInvalidPayloadError,
    WebhookInvalidSentAtError,
    WebhookMissingKeyError,
)
from affinity.inbound_webhooks import (
    BodyRegistry,
    FieldValueUpdatedBody,
    ListEntryCreatedBody,
    OrganizationMergedBody,
    WebhookOrganization,
    WebhookPerson,
    dispatch_webhook,
    parse_webhook,
)
from affinity.types import WebhookEvent

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "webhooks"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_webhook_envelope_timezone_is_utc_aware() -> None:
    payload = _load_fixture("organization_created.json")
    env = parse_webhook(payload)
    assert env.type == WebhookEvent.ORGANIZATION_CREATED
    assert env.sent_at.tzinfo == timezone.utc
    assert env.sent_at_epoch == payload["sent_at"]


def test_parse_webhook_accepts_bytes_and_str() -> None:
    payload = _load_fixture("person_created.json")
    raw = json.dumps(payload)
    assert parse_webhook(raw).type == WebhookEvent.PERSON_CREATED
    assert parse_webhook(raw.encode("utf-8")).type == WebhookEvent.PERSON_CREATED


def test_parse_webhook_unknown_event_type_is_tolerated() -> None:
    payload = _load_fixture("unknown_event.json")
    env = parse_webhook(payload)
    assert env.type.value == "made.up"
    assert env.type.name.startswith("UNKNOWN_")


def test_dispatch_webhook_uses_default_registry_where_available() -> None:
    merged = parse_webhook(_load_fixture("organization_merged.json"))
    parsed = dispatch_webhook(merged)
    assert parsed.type == WebhookEvent.ORGANIZATION_MERGED
    assert isinstance(parsed.body, OrganizationMergedBody)

    entry = parse_webhook(_load_fixture("list_entry_created.json"))
    parsed_entry = dispatch_webhook(entry)
    assert isinstance(parsed_entry.body, ListEntryCreatedBody)

    fv = parse_webhook(_load_fixture("field_value_updated.json"))
    parsed_fv = dispatch_webhook(fv)
    assert isinstance(parsed_fv.body, FieldValueUpdatedBody)

    person = parse_webhook(_load_fixture("person_created.json"))
    parsed_person = dispatch_webhook(person)
    assert isinstance(parsed_person.body, WebhookPerson)

    org = parse_webhook(_load_fixture("organization_created.json"))
    parsed_org = dispatch_webhook(org)
    assert isinstance(parsed_org.body, WebhookOrganization)


def test_dispatch_webhook_falls_back_to_dict_for_unknown_event() -> None:
    env = parse_webhook(_load_fixture("unknown_event.json"))
    parsed = dispatch_webhook(env)
    assert isinstance(parsed.body, dict)
    assert parsed.body["hello"] == "world"


def test_dispatch_webhook_registry_can_be_extended() -> None:
    class HelloBody(BaseModel):
        model_config = ConfigDict(extra="ignore")
        hello: str

    reg = BodyRegistry()
    reg.register("made.up", HelloBody)

    env = parse_webhook(_load_fixture("unknown_event.json"))
    parsed = dispatch_webhook(env, registry=reg)
    assert isinstance(parsed.body, HelloBody)
    assert parsed.body.hello == "world"


def test_parse_webhook_errors() -> None:
    with pytest.raises(WebhookInvalidJsonError):
        _ = parse_webhook("{")

    with pytest.raises(WebhookInvalidPayloadError):
        _ = parse_webhook("[]")

    with pytest.raises(WebhookMissingKeyError):
        _ = parse_webhook({"type": "person.created", "sent_at": 1})

    with pytest.raises(WebhookInvalidPayloadError):
        _ = parse_webhook({"type": "person.created", "body": [], "sent_at": 1})

    with pytest.raises(WebhookInvalidSentAtError):
        _ = parse_webhook({"type": "person.created", "body": {}, "sent_at": "nope"})
