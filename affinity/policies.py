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


@dataclass(frozen=True, slots=True)
class Policies:
    """Policy bundle applied to all requests made by a client."""

    write: WritePolicy = WritePolicy.ALLOW
