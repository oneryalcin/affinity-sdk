"""
Internal request pipeline primitives.

The SDK models requests/responses independently of the underlying HTTP transport
so cross-cutting behavior can be implemented as middleware.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias, TypedDict, cast

Header: TypeAlias = tuple[str, str]


class RequestContext(TypedDict, total=False):
    cache_key: str
    cache_ttl: float
    external: bool
    safe_follow: bool
    timeout_seconds: float
    tenant_hash: str


class ResponseContext(TypedDict, total=False):
    cache_hit: bool
    external: bool
    http_version: str
    request_id: str
    elapsed_seconds: float
    retry_count: int


@dataclass(slots=True)
class SDKRequest:
    method: str
    url: str
    headers: list[Header] = field(default_factory=list)
    params: Sequence[tuple[str, str]] | None = None
    json: Any | None = None
    files: Mapping[str, Any] | None = None
    data: Mapping[str, Any] | None = None
    api_version: Literal["v1", "v2"] = "v2"
    write_intent: bool = False
    context: RequestContext = field(default_factory=lambda: cast(RequestContext, {}))


@dataclass(slots=True)
class SDKResponse:
    status_code: int
    headers: list[Header]
    content: bytes
    json: Any | None = None
    context: ResponseContext = field(default_factory=lambda: cast(ResponseContext, {}))


Pipeline: TypeAlias = Callable[[SDKRequest], SDKResponse]
AsyncPipeline: TypeAlias = Callable[[SDKRequest], Awaitable[SDKResponse]]


class Middleware(Protocol):
    def __call__(self, req: SDKRequest, next: Pipeline) -> SDKResponse: ...


class AsyncMiddleware(Protocol):
    async def __call__(self, req: SDKRequest, next: AsyncPipeline) -> SDKResponse: ...


def compose(middlewares: Sequence[Middleware], terminal: Pipeline) -> Pipeline:
    pipeline = terminal
    for middleware in reversed(middlewares):
        next_pipeline = pipeline

        def _wrapped(
            req: SDKRequest, *, _mw: Middleware = middleware, _n: Pipeline = next_pipeline
        ) -> SDKResponse:
            return _mw(req, _n)

        pipeline = _wrapped
    return pipeline


def compose_async(middlewares: Sequence[AsyncMiddleware], terminal: AsyncPipeline) -> AsyncPipeline:
    pipeline = terminal
    for middleware in reversed(middlewares):
        next_pipeline = pipeline

        async def _wrapped(
            req: SDKRequest,
            *,
            _mw: AsyncMiddleware = middleware,
            _n: AsyncPipeline = next_pipeline,
        ) -> SDKResponse:
            return await _mw(req, _n)

        pipeline = _wrapped
    return pipeline
