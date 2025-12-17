"""
HTTP client implementation for the Affinity API.

Handles:
- Authentication
- Rate limiting with automatic retries
- Request/response logging
- V1/V2 API routing
- Optional response caching
- Request/response hooks (DX-008)
"""

from __future__ import annotations

import asyncio
import email.utils
import hashlib
import logging
import math
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, TypeAlias, TypeVar, cast
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from ..exceptions import (
    AffinityError,
    ErrorDiagnostics,
    NetworkError,
    RateLimitError,
    TimeoutError,
    UnsafeUrlError,
    VersionCompatibilityError,
    error_from_response,
)
from ..models.types import V1_BASE_URL, V2_BASE_URL
from ..progress import ProgressCallback

logger = logging.getLogger("affinity_sdk")

RepeatableQueryParam: TypeAlias = Literal["fieldIds", "fieldTypes"]
REPEATABLE_QUERY_PARAMS: frozenset[str] = frozenset({"fieldIds", "fieldTypes"})

_RETRYABLE_METHODS: frozenset[str] = frozenset({"GET", "HEAD"})
_MAX_RETRY_DELAY_SECONDS: float = 60.0
_MAX_DOWNLOAD_REDIRECTS: int = 10


T = TypeVar("T")


# =============================================================================
# Request/Response Hooks (DX-008)
# =============================================================================


@dataclass
class RequestInfo:
    """
    Sanitized request metadata for hooks.

    Note: API key is NOT included for security.
    """

    method: str
    url: str
    headers: dict[str, str]  # Redacted (no auth)


@dataclass
class ResponseInfo:
    """
    Sanitized response metadata for hooks.
    """

    status_code: int
    headers: dict[str, str]
    elapsed_ms: float
    request: RequestInfo


# Hook callback types
RequestHook: TypeAlias = Callable[[RequestInfo], None]
ResponseHook: TypeAlias = Callable[[ResponseInfo], None]


def _to_wire_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _encode_query_params(
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> list[tuple[str, str]] | None:
    """
    Convert params into deterministic ordered key/value pairs for `httpx`.

    - Repeatable params are encoded as repeated keys (e.g., fieldIds=a&fieldIds=b).
    - Repeatable values are de-duplicated while preserving caller order.
    - Non-repeatable params are emitted in sorted-key order for determinism.
    """
    if params is None:
        return None

    if isinstance(params, Mapping):
        ordered: list[tuple[str, str]] = []
        for key in sorted(params.keys()):
            value = params[key]
            if value is None:
                continue

            if key in REPEATABLE_QUERY_PARAMS:
                raw_values: Sequence[Any]
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    raw_values = value
                else:
                    raw_values = [value]

                seen: set[str] = set()
                for item in raw_values:
                    wire = _to_wire_value(item)
                    if wire in seen:
                        continue
                    ordered.append((key, wire))
                    seen.add(wire)
            else:
                ordered.append((key, _to_wire_value(value)))
        return ordered

    return [(key, _to_wire_value(value)) for key, value in params]


def _freeze_v1_query_signature(
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> list[tuple[str, str]]:
    """
    Freeze the canonical v1 query signature for token pagination.

    The returned sequence MUST NOT include the v1 `page_token` param so that the
    signature can be reused verbatim across pages (TR-017/TR-017a).
    """
    encoded = _encode_query_params(params) or []
    return [(key, value) for (key, value) in encoded if key != "page_token"]


def _compute_backoff_seconds(attempt: int, *, base: float) -> float:
    # "Full jitter": random(0, min(cap, base * 2^attempt))
    max_delay = min(_MAX_RETRY_DELAY_SECONDS, base * (2**attempt))
    jitter = (time.time_ns() % 1_000_000) / 1_000_000.0
    return cast(float, jitter * max_delay)


def _parse_retry_after(value: str) -> int | None:
    """
    Parse `Retry-After` header per RFC7231.

    Supports:
    - delta-seconds (e.g. "60")
    - HTTP-date (e.g. "Wed, 21 Oct 2015 07:28:00 GMT")
    """
    candidate = value.strip()
    if not candidate:
        return None

    if candidate.isdigit():
        return int(candidate)

    try:
        parsed = email.utils.parsedate_to_datetime(candidate)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = (parsed.astimezone(timezone.utc) - now).total_seconds()
    return max(0, math.ceil(delta))


def _default_port(scheme: str) -> int | None:
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _host_port(url: str) -> tuple[str, int | None]:
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port
    if port is None:
        port = _default_port(parts.scheme)
    return (host, port)


def _safe_follow_url(
    url: str,
    *,
    v1_base_url: str,
    v2_base_url: str,
) -> tuple[str, bool]:
    """
    Validate and normalize a server-provided URL under SafeFollowUrl policy.

    Returns: (absolute_url_without_fragment, is_v1)
    """
    v1_base = v1_base_url.rstrip("/") + "/"
    v2_base = v2_base_url.rstrip("/") + "/"

    parsed = urlsplit(url)
    # Relative URL: resolve against v2 base by default (v2 pagination/task URLs)
    absolute = urljoin(v2_base, url) if not parsed.scheme and not parsed.netloc else url

    parts = urlsplit(absolute)
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("Refusing URL with userinfo", url=absolute)

    # Strip fragments (never sent, never used for routing decisions)
    absolute = urlunsplit(parts._replace(fragment=""))
    parts = urlsplit(absolute)

    v2_parts = urlsplit(v2_base)
    v1_parts = urlsplit(v1_base)

    v2_host, v2_port = _host_port(v2_base)
    v1_host, v1_port = _host_port(v1_base)
    host, port = _host_port(absolute)

    if host not in {v1_host, v2_host} or port not in {v1_port, v2_port}:
        raise UnsafeUrlError("Refusing URL with unexpected host", url=absolute)

    v2_prefix = (v2_parts.path or "").rstrip("/") + "/"
    is_v1 = not (parts.path or "").startswith(v2_prefix)
    expected_scheme = v1_parts.scheme if is_v1 else v2_parts.scheme
    if parts.scheme != expected_scheme:
        raise UnsafeUrlError("Refusing URL with unexpected scheme", url=absolute)

    return absolute, is_v1


def _redact_url(url: str, api_key: str) -> str:
    parts = urlsplit(url)
    query_params = []
    if parts.query:
        for pair in parts.query.split("&"):
            if "=" in pair:
                key, _value = pair.split("=", 1)
                lowered = key.lower()
                if any(token in lowered for token in ("key", "token", "authorization")):
                    query_params.append(f"{key}=[REDACTED]")
                else:
                    query_params.append(pair)
            else:
                query_params.append(pair)
    redacted = urlunsplit(
        parts._replace(
            netloc=parts.hostname or parts.netloc,
            query="&".join(query_params),
        )
    )
    return redacted.replace(api_key, "[REDACTED]")


def _select_response_headers(headers: httpx.Headers) -> dict[str, str]:
    allow = [
        "Retry-After",
        "Date",
        "X-Ratelimit-Limit-User",
        "X-Ratelimit-Limit-User-Remaining",
        "X-Ratelimit-Limit-User-Reset",
        "X-Ratelimit-Limit-Org",
        "X-Ratelimit-Limit-Org-Remaining",
        "X-Ratelimit-Limit-Org-Reset",
        "X-Request-Id",
        "Request-Id",
    ]
    selected: dict[str, str] = {}
    for name in allow:
        value = headers.get(name) or headers.get(name.lower())
        if value is not None:
            selected[name] = value
    return selected


def _extract_request_id(headers: dict[str, str]) -> str | None:
    for key in ("X-Request-Id", "Request-Id"):
        if key in headers:
            return headers[key]
    return None


def _redact_external_url(url: str) -> str:
    """
    Redact external URLs for logs/diagnostics.

    External download URLs are often signed; stripping the query avoids leaking tokens.
    """
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


# =============================================================================
# Rate Limit Tracking
# =============================================================================


@dataclass
class RateLimitState:
    """Tracks rate limit status from response headers."""

    user_limit: int = 900
    user_remaining: int = 900
    user_reset_seconds: int = 60
    org_limit: int = 100_000
    org_remaining: int = 100_000
    org_reset_seconds: int = 2_592_000  # ~30 days
    last_updated: float = field(default_factory=time.time)

    def update_from_headers(self, headers: httpx.Headers) -> None:
        """Update state from response headers."""
        self.last_updated = time.time()

        # Handle both uppercase (current) and lowercase (future) headers
        def get_header(name: str) -> int | None:
            value = headers.get(name) or headers.get(name.lower())
            return int(value) if value else None

        if (v := get_header("X-Ratelimit-Limit-User")) is not None:
            self.user_limit = v
        if (v := get_header("X-Ratelimit-Limit-User-Remaining")) is not None:
            self.user_remaining = v
        if (v := get_header("X-Ratelimit-Limit-User-Reset")) is not None:
            self.user_reset_seconds = v
        if (v := get_header("X-Ratelimit-Limit-Org")) is not None:
            self.org_limit = v
        if (v := get_header("X-Ratelimit-Limit-Org-Remaining")) is not None:
            self.org_remaining = v
        if (v := get_header("X-Ratelimit-Limit-Org-Reset")) is not None:
            self.org_reset_seconds = v

    @property
    def should_throttle(self) -> bool:
        """Whether we should slow down requests."""
        return self.user_remaining < 50 or self.org_remaining < 1000

    @property
    def seconds_until_user_reset(self) -> float:
        """Seconds until per-minute limit resets."""
        elapsed = time.time() - self.last_updated
        return max(0, self.user_reset_seconds - elapsed)


# =============================================================================
# Simple TTL Cache
# =============================================================================


@dataclass
class CacheEntry:
    """Single cache entry with TTL."""

    value: dict[str, Any]
    expires_at: float


class SimpleCache:
    """
    Simple in-memory cache with TTL.

    Used for caching field metadata and other rarely-changing data.
    """

    def __init__(self, default_ttl: float = 300.0):
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> dict[str, Any] | None:
        """Get value if not expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._cache[key]
            return None
        return entry.value

    def set(self, key: str, value: dict[str, Any], ttl: float | None = None) -> None:
        """Set value with TTL."""
        expires_at = time.time() + (ttl or self._default_ttl)
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all entries with the given prefix."""
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]


# =============================================================================
# HTTP Client Configuration
# =============================================================================


@dataclass
class ClientConfig:
    """Configuration for the HTTP client."""

    api_key: str
    v1_base_url: str = V1_BASE_URL
    v2_base_url: str = V2_BASE_URL
    http2: bool = False
    v1_auth_mode: Literal["bearer", "basic"] = "bearer"
    timeout: httpx.Timeout | float = field(
        default_factory=lambda: httpx.Timeout(
            30.0,
            connect=10.0,
            read=30.0,
            write=30.0,
            pool=10.0,
        )
    )
    limits: httpx.Limits = field(
        default_factory=lambda: httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=30.0,
        )
    )
    transport: httpx.BaseTransport | None = None
    async_transport: httpx.AsyncBaseTransport | None = None
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_cache: bool = False
    cache_ttl: float = 300.0
    log_requests: bool = False
    enable_beta_endpoints: bool = False
    # If True, allows following `http://` redirects when downloading files (not recommended).
    allow_insecure_download_redirects: bool = False
    # Request/response hooks (DX-008)
    on_request: RequestHook | None = None
    on_response: ResponseHook | None = None
    # TR-015: Expected v2 API version for diagnostics and safety checks
    expected_v2_version: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.timeout, (int, float)):
            self.timeout = httpx.Timeout(float(self.timeout))


def _cache_key_suffix(v1_base_url: str, v2_base_url: str, api_key: str) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return f"|v1={v1_base_url}|v2={v2_base_url}|tenant={digest}"


# =============================================================================
# Synchronous HTTP Client
# =============================================================================


class HTTPClient:
    """
    Synchronous HTTP client for Affinity API.

    Handles authentication, rate limiting, retries, and caching.
    """

    def __init__(self, config: ClientConfig):
        self._config = config
        self._rate_limit = RateLimitState()
        self._cache = SimpleCache(config.cache_ttl) if config.enable_cache else None
        self._cache_suffix = _cache_key_suffix(
            self._config.v1_base_url,
            self._config.v2_base_url,
            self._config.api_key,
        )

        # Configure httpx client (auth is applied per-request)
        self._client = httpx.Client(
            http2=config.http2,
            timeout=config.timeout,
            limits=config.limits,
            transport=config.transport,
            headers={
                "Accept": "application/json",
            },
        )

    def _apply_auth(
        self,
        *,
        v1: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        request_kwargs = dict(kwargs)
        if v1 and self._config.v1_auth_mode == "basic":
            request_kwargs["auth"] = httpx.BasicAuth("", self._config.api_key)
            return request_kwargs

        headers = dict(request_kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self._config.api_key}"
        request_kwargs["headers"] = headers
        return request_kwargs

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def cache(self) -> SimpleCache | None:
        """Access to the cache for invalidation."""
        return self._cache

    @property
    def rate_limit_state(self) -> RateLimitState:
        """Current rate limit state."""
        return self._rate_limit

    @property
    def enable_beta_endpoints(self) -> bool:
        """Whether beta endpoints are enabled for this client."""
        return self._config.enable_beta_endpoints

    def _build_url(self, path: str, *, v1: bool = False) -> str:
        """Build full URL from path."""
        base = self._config.v1_base_url if v1 else self._config.v2_base_url
        # V1 paths don't have /v1 prefix in the base URL
        if v1:
            return f"{base}/{path.lstrip('/')}"
        return f"{base}/{path.lstrip('/')}"

    def _handle_response(
        self,
        response: httpx.Response,
        *,
        method: str,
        url: str,
        v1: bool,
    ) -> dict[str, Any]:
        """Process response and handle errors."""
        # Update rate limit state
        self._rate_limit.update_from_headers(response.headers)

        # Check for errors
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"message": response.text}

            retry_after = None
            if response.status_code == 429:
                header_value = response.headers.get("Retry-After")
                if header_value is not None:
                    retry_after = _parse_retry_after(header_value)

            selected_headers = _select_response_headers(response.headers)
            request_id = _extract_request_id(selected_headers)
            diagnostics = ErrorDiagnostics(
                method=method,
                url=_redact_url(url, self._config.api_key),
                api_version="v1" if v1 else "v2",
                base_url=self._config.v1_base_url if v1 else self._config.v2_base_url,
                request_id=request_id,
                http_version=response.http_version,
                response_headers=selected_headers,
                response_body_snippet=str(body)[:512].replace(self._config.api_key, "[REDACTED]"),
            )

            raise error_from_response(
                response.status_code,
                body,
                retry_after=retry_after,
                diagnostics=diagnostics,
            )

        # Empty response (204 No Content, etc.)
        if response.status_code == 204 or not response.content:
            return {}

        payload = response.json()
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
        if isinstance(payload, list):
            # Some V1 endpoints return top-level arrays. Normalize into an object
            # wrapper so call sites can consistently access `data`.
            return {"data": payload}
        raise AffinityError("Expected JSON object/array response")

    def _raise_for_status_with_diagnostics(
        self,
        response: httpx.Response,
        *,
        method: str,
        url: str,
        v1: bool,
        external: bool = False,
    ) -> None:
        if response.status_code < 400:
            return

        try:
            body = response.json()
        except Exception:
            body = {"message": response.text}

        retry_after = None
        if response.status_code == 429:
            header_value = response.headers.get("Retry-After")
            if header_value is not None:
                retry_after = _parse_retry_after(header_value)

        selected_headers = _select_response_headers(response.headers)
        request_id = _extract_request_id(selected_headers)

        if external:
            api_version = "external"
            base_url = f"{response.url.scheme}://{response.url.host}"
            redacted_url = _redact_external_url(str(response.url))
        else:
            api_version = "v1" if v1 else "v2"
            base_url = self._config.v1_base_url if v1 else self._config.v2_base_url
            redacted_url = _redact_url(url, self._config.api_key)

        diagnostics = ErrorDiagnostics(
            method=method,
            url=redacted_url,
            api_version=api_version,
            base_url=base_url,
            request_id=request_id,
            http_version=response.http_version,
            response_headers=selected_headers,
            response_body_snippet=str(body)[:512].replace(self._config.api_key, "[REDACTED]"),
        )

        raise error_from_response(
            response.status_code,
            body,
            retry_after=retry_after,
            diagnostics=diagnostics,
        )

    def _request_raw_with_retry(
        self,
        method: str,
        url: str,
        *,
        v1: bool,
        apply_auth: bool,
        follow_redirects: bool,
        allow_hooks: bool,
        external: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a request with retry policy, returning the raw `httpx.Response`.

        Used for file download/streaming where the response is not JSON.
        """
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                if self._config.log_requests and not external:
                    logger.debug(f"{method} {url}")

                request_kwargs = dict(kwargs)
                if apply_auth:
                    request_kwargs = self._apply_auth(v1=v1, kwargs=request_kwargs)
                request_kwargs["follow_redirects"] = follow_redirects

                if allow_hooks and self._config.on_request and not external:
                    sanitized_headers = {
                        k: v
                        for k, v in (request_kwargs.get("headers", {}) or {}).items()
                        if k.lower() != "authorization"
                    }
                    if "auth" in request_kwargs:
                        sanitized_headers["Authorization"] = "[REDACTED]"
                    req_info = RequestInfo(
                        method=method,
                        url=_redact_url(url, self._config.api_key),
                        headers=sanitized_headers,
                    )
                    self._config.on_request(req_info)

                start_time = time.monotonic()
                response = self._client.request(method, url, **request_kwargs)
                elapsed_ms = (time.monotonic() - start_time) * 1000

                if allow_hooks and self._config.on_response and not external:
                    resp_info = ResponseInfo(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        elapsed_ms=elapsed_ms,
                        request=RequestInfo(
                            method=method,
                            url=_redact_url(url, self._config.api_key),
                            headers={},
                        ),
                    )
                    self._config.on_response(resp_info)

                if not external:
                    self._rate_limit.update_from_headers(response.headers)

                self._raise_for_status_with_diagnostics(
                    response,
                    method=method,
                    url=url,
                    v1=v1,
                    external=external,
                )
                return response

            except RateLimitError as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise
                if attempt >= self._config.max_retries:
                    break
                wait_time = (
                    float(e.retry_after)
                    if e.retry_after is not None
                    else _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                )
                logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                time.sleep(wait_time)

            except AffinityError as e:
                last_error = e
                status = e.status_code
                if (
                    method not in _RETRYABLE_METHODS
                    or status is None
                    or status < 500
                    or status >= 600
                ):
                    raise
                if attempt >= self._config.max_retries:
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                logger.warning(
                    f"Server error {status}, waiting {wait_time}s (attempt {attempt + 1})"
                )
                time.sleep(wait_time)

            except httpx.TimeoutException as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise TimeoutError(f"Request timed out: {e}") from e
                if attempt >= self._config.max_retries:
                    timeout_error = TimeoutError(f"Request timed out: {e}")
                    timeout_error.__cause__ = e
                    last_error = timeout_error
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                time.sleep(wait_time)

            except httpx.NetworkError as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise NetworkError(f"Network error: {e}") from e
                if attempt >= self._config.max_retries:
                    network_error = NetworkError(f"Network error: {e}")
                    network_error.__cause__ = e
                    last_error = network_error
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                time.sleep(wait_time)

        if last_error:
            raise last_error
        raise AffinityError("Request failed after retries")

    def _get_download_redirect_url(self, response: httpx.Response) -> str | None:
        """Return the absolute redirect URL for a download response (if any)."""
        location = response.headers.get("Location")
        if not location:
            return None

        redirect_url = str(urljoin(str(response.url), location))
        scheme = urlsplit(redirect_url).scheme.lower()
        if scheme and scheme not in ("https", "http"):
            raise UnsafeUrlError("Refusing to follow non-http(s) redirect", url=redirect_url)
        if scheme == "http" and not self._config.allow_insecure_download_redirects:
            raise UnsafeUrlError(
                "Refusing to follow non-https redirect for download",
                url=_redact_external_url(redirect_url),
            )
        return redirect_url

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        v1: bool,
        safe_follow: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make request with retry policy for safe methods."""
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                if self._config.log_requests:
                    logger.debug(f"{method} {url}")

                request_kwargs = self._apply_auth(v1=v1, kwargs=kwargs)
                if safe_follow:
                    request_kwargs["follow_redirects"] = False

                # Call request hook (DX-008)
                if self._config.on_request:
                    # Build sanitized headers (no auth)
                    sanitized_headers = {
                        k: v
                        for k, v in request_kwargs.get("headers", {}).items()
                        if k.lower() != "authorization"
                    }
                    req_info = RequestInfo(
                        method=method,
                        url=_redact_url(url, self._config.api_key),
                        headers=sanitized_headers,
                    )
                    self._config.on_request(req_info)

                start_time = time.monotonic()
                response = self._client.request(method, url, **request_kwargs)
                elapsed_ms = (time.monotonic() - start_time) * 1000

                # Call response hook (DX-008)
                if self._config.on_response:
                    resp_info = ResponseInfo(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        elapsed_ms=elapsed_ms,
                        request=RequestInfo(
                            method=method,
                            url=_redact_url(url, self._config.api_key),
                            headers={},
                        ),
                    )
                    self._config.on_response(resp_info)

                if safe_follow and response.is_redirect:
                    raise UnsafeUrlError(
                        "Refusing to follow redirect for server-provided URL",
                        url=url,
                    )
                return self._handle_response(
                    response,
                    method=method,
                    url=url,
                    v1=v1,
                )

            except RateLimitError as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise
                if attempt >= self._config.max_retries:
                    break
                wait_time = (
                    float(e.retry_after)
                    if e.retry_after is not None
                    else _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                )
                logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                time.sleep(wait_time)

            except AffinityError as e:
                last_error = e
                status = e.status_code
                if (
                    method not in _RETRYABLE_METHODS
                    or status is None
                    or status < 500
                    or status >= 600
                ):
                    raise
                if attempt >= self._config.max_retries:
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                logger.warning(
                    f"Server error {status}, waiting {wait_time}s (attempt {attempt + 1})"
                )
                time.sleep(wait_time)

            except httpx.TimeoutException as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise TimeoutError(f"Request timed out: {e}") from e
                if attempt >= self._config.max_retries:
                    timeout_error = TimeoutError(f"Request timed out: {e}")
                    timeout_error.__cause__ = e
                    last_error = timeout_error
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                time.sleep(wait_time)

            except httpx.NetworkError as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise NetworkError(f"Network error: {e}") from e
                if attempt >= self._config.max_retries:
                    network_error = NetworkError(f"Network error: {e}")
                    network_error.__cause__ = e
                    last_error = network_error
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                time.sleep(wait_time)

        # Exhausted retries
        if last_error:
            raise last_error
        raise AffinityError("Request failed after retries")

    # =========================================================================
    # Public Request Methods
    # =========================================================================

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        v1: bool = False,
        cache_key: str | None = None,
        cache_ttl: float | None = None,
    ) -> dict[str, Any]:
        """
        Make a GET request.

        Args:
            path: API path (e.g., "/companies")
            params: Query parameters
            v1: Use V1 API endpoint
            cache_key: If provided, cache the response with this key
            cache_ttl: Cache TTL override

        Returns:
            Parsed JSON response
        """
        # Check cache
        if cache_key and self._cache:
            cached = self._cache.get(f"{cache_key}{self._cache_suffix}")
            if cached is not None:
                return cached

        url = self._build_url(path, v1=v1)
        encoded_params = _encode_query_params(params)
        result = self._request_with_retry("GET", url, v1=v1, params=encoded_params)

        # Store in cache
        if cache_key and self._cache and result is not None:
            self._cache.set(f"{cache_key}{self._cache_suffix}", result, cache_ttl)

        return result

    def get_v1_page(
        self,
        path: str,
        *,
        signature: Sequence[tuple[str, str]],
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a v1 paginated page using a frozen canonical query signature.

        This enforces TR-017a by reusing the exact same query signature across
        pages, varying only the `page_token`.
        """
        params = list(signature)
        if page_token is not None:
            params.append(("page_token", page_token))
        url = self._build_url(path, v1=True)
        return self._request_with_retry("GET", url, v1=True, params=params)

    def get_url(self, url: str) -> dict[str, Any]:
        """
        Make a GET request to a full URL.

        Used for following pagination URLs.
        """
        absolute, is_v1 = _safe_follow_url(
            url,
            v1_base_url=self._config.v1_base_url,
            v2_base_url=self._config.v2_base_url,
        )
        return self._request_with_retry("GET", absolute, v1=is_v1, safe_follow=True)

    def post(
        self,
        path: str,
        *,
        json: Any = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        """Make a POST request."""
        url = self._build_url(path, v1=v1)
        return self._request_with_retry("POST", url, v1=v1, json=json)

    def put(
        self,
        path: str,
        *,
        json: Any = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        """Make a PUT request."""
        url = self._build_url(path, v1=v1)
        return self._request_with_retry("PUT", url, v1=v1, json=json)

    def patch(
        self,
        path: str,
        *,
        json: Any = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        """Make a PATCH request."""
        url = self._build_url(path, v1=v1)
        return self._request_with_retry("PATCH", url, v1=v1, json=json)

    def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        """Make a DELETE request."""
        url = self._build_url(path, v1=v1)
        return self._request_with_retry("DELETE", url, v1=v1, params=_encode_query_params(params))

    def upload_file(
        self,
        path: str,
        *,
        files: dict[str, Any],
        data: dict[str, Any] | None = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        """Upload files with multipart form data."""
        url = self._build_url(path, v1=v1)

        # Remove Content-Type header for multipart
        headers = dict(self._client.headers)
        headers.pop("Content-Type", None)
        return self._request_with_retry(
            "POST",
            url,
            v1=v1,
            files=files,
            data=data,
            headers=headers,
        )

    def download_file(
        self,
        path: str,
        *,
        v1: bool = False,
    ) -> bytes:
        """
        Download file content.

        Notes:
        - The initial Affinity API response may redirect to an external signed URL.
          Redirects are followed without forwarding credentials.
        - Uses the standard retry/diagnostics policy for GET requests.
        """
        url = self._build_url(path, v1=v1)
        response = self._request_raw_with_retry(
            "GET",
            url,
            v1=v1,
            apply_auth=True,
            follow_redirects=False,
            allow_hooks=False,
            external=False,
        )
        if response.is_redirect:
            redirect_url = self._get_download_redirect_url(response)
            if redirect_url is not None:
                current_url = redirect_url
                for _ in range(_MAX_DOWNLOAD_REDIRECTS + 1):
                    response = self._request_raw_with_retry(
                        "GET",
                        current_url,
                        v1=v1,
                        apply_auth=False,
                        follow_redirects=False,
                        allow_hooks=False,
                        external=True,
                    )
                    if not response.is_redirect:
                        break
                    next_url = self._get_download_redirect_url(response)
                    if next_url is None:
                        break
                    current_url = next_url

                if (
                    response.url.scheme.lower() != "https"
                    and not self._config.allow_insecure_download_redirects
                ):
                    raise UnsafeUrlError(
                        "Refusing to download from non-https URL",
                        url=_redact_external_url(str(response.url)),
                    )

        return response.content

    def stream_download(
        self,
        path: str,
        *,
        v1: bool = False,
        chunk_size: int = 65_536,
        on_progress: ProgressCallback | None = None,
    ) -> Iterator[bytes]:
        """
        Stream-download file content in chunks.

        Notes:
        - The initial Affinity API response may redirect to an external signed URL.
          Redirects are followed without forwarding credentials.
        - Download traffic intentionally does not call request/response hooks to
          avoid leaking signed URLs in logs.
        """
        url = self._build_url(path, v1=v1)

        response = self._request_raw_with_retry(
            "GET",
            url,
            v1=v1,
            apply_auth=True,
            follow_redirects=False,
            allow_hooks=False,
            external=False,
        )

        if response.is_redirect:
            redirect_url = self._get_download_redirect_url(response)
            if redirect_url is None:
                return

            yielded_any = False
            last_error: Exception | None = None
            for attempt in range(self._config.max_retries + 1):
                try:
                    current_url = redirect_url
                    redirects_followed = 0
                    while True:
                        if redirects_followed > _MAX_DOWNLOAD_REDIRECTS:
                            raise UnsafeUrlError(
                                "Refusing to follow too many redirects for download",
                                url=_redact_external_url(current_url),
                            )
                        if (
                            urlsplit(current_url).scheme.lower() == "http"
                            and not self._config.allow_insecure_download_redirects
                        ):
                            raise UnsafeUrlError(
                                "Refusing to download from non-https URL",
                                url=_redact_external_url(current_url),
                            )

                        with self._client.stream(
                            "GET",
                            current_url,
                            follow_redirects=False,
                        ) as streamed:
                            if streamed.is_redirect:
                                next_url = self._get_download_redirect_url(streamed)
                                if next_url is None:
                                    return
                                current_url = next_url
                                redirects_followed += 1
                                continue

                            if (
                                streamed.url.scheme.lower() != "https"
                                and not self._config.allow_insecure_download_redirects
                            ):
                                raise UnsafeUrlError(
                                    "Refusing to download from non-https URL",
                                    url=_redact_external_url(str(streamed.url)),
                                )
                            self._raise_for_status_with_diagnostics(
                                streamed,
                                method="GET",
                                url=current_url,
                                v1=v1,
                                external=True,
                            )
                            stream_total: int | None = None
                            if on_progress:
                                raw_total = streamed.headers.get("Content-Length")
                                if raw_total and raw_total.isdigit():
                                    stream_total = int(raw_total)
                                on_progress(0, stream_total, phase="download")
                            transferred = 0
                            for chunk in streamed.iter_bytes(chunk_size=chunk_size):
                                yielded_any = True
                                transferred += len(chunk)
                                if on_progress:
                                    on_progress(transferred, stream_total, phase="download")
                                yield chunk
                            return
                except RateLimitError as e:
                    last_error = e
                    if yielded_any:
                        raise
                    if attempt >= self._config.max_retries:
                        break
                    wait_time = (
                        float(e.retry_after)
                        if e.retry_after is not None
                        else _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                    )
                    time.sleep(wait_time)
                except AffinityError as e:
                    last_error = e
                    status = e.status_code
                    if yielded_any or status is None or status < 500 or status >= 600:
                        raise
                    if attempt >= self._config.max_retries:
                        break
                    wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                    time.sleep(wait_time)
                except httpx.TimeoutException as e:
                    last_error = e
                    if yielded_any:
                        raise TimeoutError(f"Request timed out: {e}") from e
                    if attempt >= self._config.max_retries:
                        timeout_error = TimeoutError(f"Request timed out: {e}")
                        timeout_error.__cause__ = e
                        last_error = timeout_error
                        break
                    wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                    time.sleep(wait_time)
                except httpx.NetworkError as e:
                    last_error = e
                    if yielded_any:
                        raise NetworkError(f"Network error: {e}") from e
                    if attempt >= self._config.max_retries:
                        network_error = NetworkError(f"Network error: {e}")
                        network_error.__cause__ = e
                        last_error = network_error
                        break
                    wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                    time.sleep(wait_time)

            if last_error:
                raise last_error
            raise AffinityError("Download failed after retries")

        total: int | None = None
        if on_progress:
            raw_total = response.headers.get("Content-Length")
            if raw_total and raw_total.isdigit():
                total = int(raw_total)
            on_progress(0, total, phase="download")
        transferred = 0
        for chunk in response.iter_bytes(chunk_size=chunk_size):
            transferred += len(chunk)
            if on_progress:
                on_progress(transferred, total, phase="download")
            yield chunk

    def wrap_validation_error(
        self,
        error: Exception,
        *,
        context: str | None = None,
    ) -> VersionCompatibilityError:
        """
        Wrap a validation error with version compatibility context.

        TR-015: If expected_v2_version is configured, validation failures
        are wrapped with actionable guidance about checking API version.
        """
        expected = self._config.expected_v2_version
        message = (
            f"Response parsing failed: {error}. "
            "This may indicate a v2 API version mismatch. "
            "Check your API key's Default API Version in the Affinity dashboard."
        )
        if context:
            message = f"[{context}] {message}"
        return VersionCompatibilityError(
            message,
            expected_version=expected,
            parsing_error=str(error),
        )

    @property
    def expected_v2_version(self) -> str | None:
        """Expected V2 API version for diagnostics."""
        return self._config.expected_v2_version


# =============================================================================
# Asynchronous HTTP Client
# =============================================================================


class AsyncHTTPClient:
    """
    Asynchronous HTTP client for Affinity API.

    Same functionality as HTTPClient but with async/await support.
    """

    def __init__(self, config: ClientConfig):
        self._config = config
        self._rate_limit = RateLimitState()
        self._cache = SimpleCache(config.cache_ttl) if config.enable_cache else None
        self._cache_suffix = _cache_key_suffix(
            self._config.v1_base_url,
            self._config.v2_base_url,
            self._config.api_key,
        )
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=self._config.http2,
                timeout=self._config.timeout,
                limits=self._config.limits,
                transport=self._config.async_transport,
                headers={
                    "Accept": "application/json",
                },
            )
        return self._client

    def _apply_auth(
        self,
        *,
        v1: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        request_kwargs = dict(kwargs)
        if v1 and self._config.v1_auth_mode == "basic":
            request_kwargs["auth"] = httpx.BasicAuth("", self._config.api_key)
            return request_kwargs

        headers = dict(request_kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self._config.api_key}"
        request_kwargs["headers"] = headers
        return request_kwargs

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> AsyncHTTPClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @property
    def cache(self) -> SimpleCache | None:
        return self._cache

    @property
    def rate_limit_state(self) -> RateLimitState:
        return self._rate_limit

    @property
    def enable_beta_endpoints(self) -> bool:
        return self._config.enable_beta_endpoints

    def _build_url(self, path: str, *, v1: bool = False) -> str:
        base = self._config.v1_base_url if v1 else self._config.v2_base_url
        if v1:
            return f"{base}/{path.lstrip('/')}"
        return f"{base}/{path.lstrip('/')}"

    def _handle_response(
        self,
        response: httpx.Response,
        *,
        method: str,
        url: str,
        v1: bool,
    ) -> dict[str, Any]:
        self._rate_limit.update_from_headers(response.headers)

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"message": response.text}

            retry_after = None
            if response.status_code == 429:
                header_value = response.headers.get("Retry-After")
                if header_value is not None:
                    retry_after = _parse_retry_after(header_value)

            selected_headers = _select_response_headers(response.headers)
            request_id = _extract_request_id(selected_headers)
            diagnostics = ErrorDiagnostics(
                method=method,
                url=_redact_url(url, self._config.api_key),
                api_version="v1" if v1 else "v2",
                base_url=self._config.v1_base_url if v1 else self._config.v2_base_url,
                request_id=request_id,
                http_version=response.http_version,
                response_headers=selected_headers,
                response_body_snippet=str(body)[:512].replace(self._config.api_key, "[REDACTED]"),
            )

            raise error_from_response(
                response.status_code,
                body,
                retry_after=retry_after,
                diagnostics=diagnostics,
            )

        if response.status_code == 204 or not response.content:
            return {}

        payload = response.json()
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
        if isinstance(payload, list):
            return {"data": payload}
        raise AffinityError("Expected JSON object/array response")

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        v1: bool,
        safe_follow: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                if self._config.log_requests:
                    logger.debug(f"{method} {url}")

                request_kwargs = self._apply_auth(v1=v1, kwargs=kwargs)
                if safe_follow:
                    request_kwargs["follow_redirects"] = False

                # Call request hook (DX-008)
                if self._config.on_request:
                    sanitized_headers = {
                        k: v
                        for k, v in request_kwargs.get("headers", {}).items()
                        if k.lower() != "authorization"
                    }
                    req_info = RequestInfo(
                        method=method,
                        url=_redact_url(url, self._config.api_key),
                        headers=sanitized_headers,
                    )
                    self._config.on_request(req_info)

                start_time = time.monotonic()
                response = await client.request(method, url, **request_kwargs)
                elapsed_ms = (time.monotonic() - start_time) * 1000

                # Call response hook (DX-008)
                if self._config.on_response:
                    resp_info = ResponseInfo(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        elapsed_ms=elapsed_ms,
                        request=RequestInfo(
                            method=method,
                            url=_redact_url(url, self._config.api_key),
                            headers={},
                        ),
                    )
                    self._config.on_response(resp_info)

                if safe_follow and response.is_redirect:
                    raise UnsafeUrlError(
                        "Refusing to follow redirect for server-provided URL",
                        url=url,
                    )
                return self._handle_response(
                    response,
                    method=method,
                    url=url,
                    v1=v1,
                )

            except RateLimitError as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise
                if attempt >= self._config.max_retries:
                    break
                wait_time = (
                    float(e.retry_after)
                    if e.retry_after is not None
                    else _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                )
                logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)

            except AffinityError as e:
                last_error = e
                status = e.status_code
                if (
                    method not in _RETRYABLE_METHODS
                    or status is None
                    or status < 500
                    or status >= 600
                ):
                    raise
                if attempt >= self._config.max_retries:
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                logger.warning(
                    f"Server error {status}, waiting {wait_time}s (attempt {attempt + 1})"
                )
                await asyncio.sleep(wait_time)

            except httpx.TimeoutException as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise TimeoutError(f"Request timed out: {e}") from e
                if attempt >= self._config.max_retries:
                    timeout_error = TimeoutError(f"Request timed out: {e}")
                    timeout_error.__cause__ = e
                    last_error = timeout_error
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                await asyncio.sleep(wait_time)

            except httpx.NetworkError as e:
                last_error = e
                if method not in _RETRYABLE_METHODS:
                    raise NetworkError(f"Network error: {e}") from e
                if attempt >= self._config.max_retries:
                    network_error = NetworkError(f"Network error: {e}")
                    network_error.__cause__ = e
                    last_error = network_error
                    break
                wait_time = _compute_backoff_seconds(attempt, base=self._config.retry_delay)
                await asyncio.sleep(wait_time)

        if last_error:
            raise last_error
        raise AffinityError("Request failed after retries")

    # =========================================================================
    # Public Request Methods
    # =========================================================================

    async def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        v1: bool = False,
        cache_key: str | None = None,
        cache_ttl: float | None = None,
    ) -> dict[str, Any]:
        if cache_key and self._cache:
            cached = self._cache.get(f"{cache_key}{self._cache_suffix}")
            if cached is not None:
                return cached

        url = self._build_url(path, v1=v1)
        encoded_params = _encode_query_params(params)
        result = await self._request_with_retry(
            "GET",
            url,
            v1=v1,
            params=encoded_params,
        )

        if cache_key and self._cache and result is not None:
            self._cache.set(f"{cache_key}{self._cache_suffix}", result, cache_ttl)

        return result

    async def get_v1_page(
        self,
        path: str,
        *,
        signature: Sequence[tuple[str, str]],
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Async version of `get_v1_page()`."""
        params = list(signature)
        if page_token is not None:
            params.append(("page_token", page_token))
        url = self._build_url(path, v1=True)
        return await self._request_with_retry("GET", url, v1=True, params=params)

    async def get_url(self, url: str) -> dict[str, Any]:
        absolute, is_v1 = _safe_follow_url(
            url,
            v1_base_url=self._config.v1_base_url,
            v2_base_url=self._config.v2_base_url,
        )
        return await self._request_with_retry(
            "GET",
            absolute,
            v1=is_v1,
            safe_follow=True,
        )

    async def post(
        self,
        path: str,
        *,
        json: Any = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        url = self._build_url(path, v1=v1)
        return await self._request_with_retry("POST", url, v1=v1, json=json)

    async def put(
        self,
        path: str,
        *,
        json: Any = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        url = self._build_url(path, v1=v1)
        return await self._request_with_retry("PUT", url, v1=v1, json=json)

    async def patch(
        self,
        path: str,
        *,
        json: Any = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        url = self._build_url(path, v1=v1)
        return await self._request_with_retry("PATCH", url, v1=v1, json=json)

    async def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        v1: bool = False,
    ) -> dict[str, Any]:
        url = self._build_url(path, v1=v1)
        return await self._request_with_retry(
            "DELETE", url, v1=v1, params=_encode_query_params(params)
        )

    def wrap_validation_error(
        self,
        error: Exception,
        *,
        context: str | None = None,
    ) -> VersionCompatibilityError:
        """
        Wrap a validation error with version compatibility context.

        TR-015: If expected_v2_version is configured, validation failures
        are wrapped with actionable guidance about checking API version.
        """
        expected = self._config.expected_v2_version
        message = (
            f"Response parsing failed: {error}. "
            "This may indicate a v2 API version mismatch. "
            "Check your API key's Default API Version in the Affinity dashboard."
        )
        if context:
            message = f"[{context}] {message}"
        return VersionCompatibilityError(
            message,
            expected_version=expected,
            parsing_error=str(error),
        )

    @property
    def expected_v2_version(self) -> str | None:
        """Expected V2 API version for diagnostics."""
        return self._config.expected_v2_version
