"""
Client policies (cross-cutting behavioral controls).

Policies are orthogonal and composable. They are enforced centrally by the HTTP
request pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WritePolicy(Enum):
    """Whether the SDK is allowed to perform write operations."""

    ALLOW = "allow"
    DENY = "deny"


class ExternalHookPolicy(Enum):
    """
    Controls hook/event emission for requests to external hosts (e.g., signed URLs).

    - SUPPRESS: do not emit hook events for external hops
    - REDACT: emit events but redact external URLs (drop query/fragment)
    - EMIT_UNSAFE: emit full external URLs (unsafe; may leak signed query params)
    """

    SUPPRESS = "suppress"
    REDACT = "redact"
    EMIT_UNSAFE = "emit_unsafe"


@dataclass(frozen=True, slots=True)
class Policies:
    """Policy bundle applied to all requests made by a client."""

    write: WritePolicy = WritePolicy.ALLOW
    external_hooks: ExternalHookPolicy = ExternalHookPolicy.REDACT
