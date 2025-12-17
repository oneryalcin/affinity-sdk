# Webhooks

The SDK supports managing webhook subscriptions via the V1 API (`client.webhooks`). Receiving webhooks is handled by **your** web server/app.

## Create a subscription

```python
from affinity import Affinity
from affinity.models import WebhookCreate
from affinity.types import WebhookEvent

with Affinity.from_env() as client:
    webhook = client.webhooks.create(
        WebhookCreate(
            webhook_url="https://example.com/webhooks/affinity/<random-secret>",
            subscriptions=[
                WebhookEvent.FIELD_VALUE_UPDATED,
                WebhookEvent.LIST_ENTRY_CREATED,
            ],
        )
    )
    print(webhook.id, webhook.webhook_url)
```

!!! note "Notes"
    - Affinity limits webhook subscriptions (see `WebhookService` docs).
    - Affinity may attempt to contact your `webhook_url` during creation/updates; ensure your endpoint is reachable and responds quickly.

## Verify inbound requests (recommended)

Affinity’s public V1 docs do not describe a standard signature scheme. If your account includes a signature header/mechanism, validate it per Affinity’s documentation.

If you do not have a signature mechanism, treat the webhook endpoint like a public entry point and add your own verification controls:

- **Use HTTPS only** (terminate TLS at a load balancer/reverse proxy if needed).
- **Use an unguessable URL** (include a random secret in the path) and reject requests missing it.
- **Validate method/content-type** and parse JSON defensively.
- **Optionally enforce a replay window** using `sent_at` (e.g., reject events older than N seconds).
- **Respond fast** (2xx) and enqueue work; assume retries can happen.
- **Avoid logging raw payloads** unless you have a PII-safe pipeline.

## Parse inbound payloads (optional)

The SDK includes small, framework-agnostic helpers to parse the webhook envelope and (optionally) dispatch to a typed body for a few common events.

```python
from affinity import dispatch_webhook, parse_webhook
from affinity.types import WebhookEvent

envelope = parse_webhook(raw_body_bytes)  # or raw str / dict
event = dispatch_webhook(envelope)  # typed for some events, dict otherwise

if event.type == WebhookEvent.LIST_ENTRY_CREATED:
    # event.body may be typed (or a dict, depending on the event)
    print(event.sent_at, event.body)
```

## Minimal receiver example (FastAPI)

```python
from fastapi import FastAPI, HTTPException, Request
from affinity import dispatch_webhook, parse_webhook

app = FastAPI()

WEBHOOK_SECRET = "replace-with-a-long-random-string"


@app.post("/webhooks/affinity/{secret}")
async def affinity_webhook(secret: str, request: Request) -> dict[str, str]:
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")

    raw = await request.body()
    envelope = parse_webhook(raw)
    event = dispatch_webhook(envelope)
    # Process `event` (shape is defined by Affinity)
    return {"ok": "true"}
```
