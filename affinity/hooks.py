"""
Public hook types for request/response instrumentation (DX-008).

This module intentionally re-exports the sanitized hook types so users don't need
to import from `affinity.clients.http` (internal implementation detail).
"""

from __future__ import annotations

from .clients.http import RequestHook, RequestInfo, ResponseHook, ResponseInfo

__all__ = [
    "RequestHook",
    "RequestInfo",
    "ResponseHook",
    "ResponseInfo",
]
