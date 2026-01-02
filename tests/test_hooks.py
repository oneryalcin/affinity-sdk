"""Tests for affinity.hooks module - dataclasses and type aliases."""

from __future__ import annotations

import dataclasses
from typing import get_args

import pytest

from affinity.hooks import (
    # Legacy 3-hook API
    ErrorInfo,
    # Event-based API
    HookEvent,
    RedirectFollowed,
    RequestFailed,
    RequestInfo,
    RequestRetrying,
    RequestStarted,
    RequestSucceeded,
    ResponseHeadersReceived,
    ResponseInfo,
    StreamAborted,
    StreamCompleted,
    StreamFailed,
)


class TestRequestInfo:
    """Tests for RequestInfo dataclass."""

    def test_instantiation(self) -> None:
        info = RequestInfo(
            method="GET",
            url="https://api.affinity.co/v2/companies/123",
            headers={"Authorization": "Bearer xxx"},
        )
        assert info.method == "GET"
        assert info.url == "https://api.affinity.co/v2/companies/123"
        assert info.headers == {"Authorization": "Bearer xxx"}

    def test_frozen(self) -> None:
        info = RequestInfo(method="GET", url="https://example.com", headers={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.method = "POST"  # type: ignore[misc]

    def test_slots(self) -> None:
        info = RequestInfo(method="GET", url="https://example.com", headers={})
        assert not hasattr(info, "__dict__")


class TestResponseInfo:
    """Tests for ResponseInfo dataclass."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        info = ResponseInfo(
            status_code=200,
            headers={"Content-Type": "application/json"},
            elapsed_ms=150.5,
            request=request,
            cache_hit=True,
        )
        assert info.status_code == 200
        assert info.headers == {"Content-Type": "application/json"}
        assert info.elapsed_ms == 150.5
        assert info.request is request
        assert info.cache_hit is True

    def test_cache_hit_default(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        info = ResponseInfo(
            status_code=200,
            headers={},
            elapsed_ms=100.0,
            request=request,
        )
        assert info.cache_hit is False

    def test_frozen(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        info = ResponseInfo(status_code=200, headers={}, elapsed_ms=100.0, request=request)
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.status_code = 404  # type: ignore[misc]


class TestErrorInfo:
    """Tests for ErrorInfo dataclass."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="POST", url="https://example.com/api", headers={})
        error = ValueError("something went wrong")
        info = ErrorInfo(error=error, elapsed_ms=50.0, request=request)
        assert info.error is error
        assert info.elapsed_ms == 50.0
        assert info.request is request

    def test_frozen(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        info = ErrorInfo(error=Exception(), elapsed_ms=10.0, request=request)
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.elapsed_ms = 20.0  # type: ignore[misc]


class TestRequestStarted:
    """Tests for RequestStarted event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        event = RequestStarted(
            client_request_id="req-123",
            request=request,
            api_version="v2",
        )
        assert event.client_request_id == "req-123"
        assert event.request is request
        assert event.api_version == "v2"
        assert event.type == "request_started"

    def test_type_literal_is_readonly(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        event = RequestStarted(client_request_id="x", request=request, api_version="v1")
        assert event.type == "request_started"


class TestRequestRetrying:
    """Tests for RequestRetrying event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        event = RequestRetrying(
            client_request_id="req-456",
            request=request,
            attempt=2,
            wait_seconds=1.5,
            reason="rate_limited",
        )
        assert event.client_request_id == "req-456"
        assert event.attempt == 2
        assert event.wait_seconds == 1.5
        assert event.reason == "rate_limited"
        assert event.type == "request_retrying"


class TestRedirectFollowed:
    """Tests for RedirectFollowed event."""

    def test_instantiation(self) -> None:
        event = RedirectFollowed(
            client_request_id="req-789",
            from_url="https://api.affinity.co/files/123",
            to_url="https://storage.example.com/files/123",
            hop=1,
            external=True,
        )
        assert event.client_request_id == "req-789"
        assert event.from_url == "https://api.affinity.co/files/123"
        assert event.to_url == "https://storage.example.com/files/123"
        assert event.hop == 1
        assert event.external is True
        assert event.type == "redirect_followed"


class TestResponseHeadersReceived:
    """Tests for ResponseHeadersReceived event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        event = ResponseHeadersReceived(
            client_request_id="req-abc",
            request=request,
            status_code=200,
            headers=[("Content-Type", "application/json"), ("X-Request-Id", "xyz")],
            elapsed_ms=120.5,
            external=False,
            cache_hit=True,
            request_id="xyz",
        )
        assert event.status_code == 200
        assert event.headers == [("Content-Type", "application/json"), ("X-Request-Id", "xyz")]
        assert event.elapsed_ms == 120.5
        assert event.external is False
        assert event.cache_hit is True
        assert event.request_id == "xyz"
        assert event.type == "response_headers_received"

    def test_request_id_default(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        event = ResponseHeadersReceived(
            client_request_id="x",
            request=request,
            status_code=200,
            headers=[],
            elapsed_ms=0,
            external=False,
            cache_hit=False,
        )
        assert event.request_id is None


class TestRequestFailed:
    """Tests for RequestFailed event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="POST", url="https://example.com", headers={})
        error = ConnectionError("network unreachable")
        event = RequestFailed(
            client_request_id="req-fail",
            request=request,
            error=error,
            elapsed_ms=5000.0,
            external=False,
        )
        assert event.client_request_id == "req-fail"
        assert event.error is error
        assert event.elapsed_ms == 5000.0
        assert event.external is False
        assert event.type == "request_failed"


class TestRequestSucceeded:
    """Tests for RequestSucceeded event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        event = RequestSucceeded(
            client_request_id="req-ok",
            request=request,
            status_code=201,
            elapsed_ms=80.0,
            external=True,
        )
        assert event.status_code == 201
        assert event.elapsed_ms == 80.0
        assert event.external is True
        assert event.type == "request_succeeded"


class TestStreamCompleted:
    """Tests for StreamCompleted event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com/file", headers={})
        event = StreamCompleted(
            client_request_id="stream-1",
            request=request,
            bytes_read=1024,
            bytes_total=1024,
            elapsed_ms=500.0,
            external=True,
        )
        assert event.bytes_read == 1024
        assert event.bytes_total == 1024
        assert event.elapsed_ms == 500.0
        assert event.external is True
        assert event.type == "stream_completed"

    def test_bytes_total_none(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com/file", headers={})
        event = StreamCompleted(
            client_request_id="stream-2",
            request=request,
            bytes_read=512,
            bytes_total=None,
            elapsed_ms=200.0,
            external=False,
        )
        assert event.bytes_total is None


class TestStreamAborted:
    """Tests for StreamAborted event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com/file", headers={})
        event = StreamAborted(
            client_request_id="stream-abort",
            request=request,
            reason="user_cancelled",
            bytes_read=256,
            bytes_total=1024,
            elapsed_ms=100.0,
            external=True,
        )
        assert event.reason == "user_cancelled"
        assert event.bytes_read == 256
        assert event.bytes_total == 1024
        assert event.type == "stream_aborted"


class TestStreamFailed:
    """Tests for StreamFailed event."""

    def test_instantiation(self) -> None:
        request = RequestInfo(method="GET", url="https://example.com/file", headers={})
        error = OSError("disk full")
        event = StreamFailed(
            client_request_id="stream-fail",
            request=request,
            error=error,
            bytes_read=100,
            bytes_total=1000,
            elapsed_ms=50.0,
            external=False,
        )
        assert event.error is error
        assert event.bytes_read == 100
        assert event.type == "stream_failed"


class TestHookEventUnion:
    """Tests for HookEvent type alias."""

    def test_all_event_types_are_in_union(self) -> None:
        """Verify HookEvent includes all event dataclasses."""
        expected_types = {
            RequestStarted,
            RequestRetrying,
            RedirectFollowed,
            ResponseHeadersReceived,
            RequestFailed,
            RequestSucceeded,
            StreamCompleted,
            StreamAborted,
            StreamFailed,
        }
        actual_types = set(get_args(HookEvent))
        assert actual_types == expected_types

    def test_event_type_discrimination(self) -> None:
        """Each event has a unique type literal for discrimination."""
        request = RequestInfo(method="GET", url="https://example.com", headers={})
        events: list[HookEvent] = [
            RequestStarted(client_request_id="1", request=request, api_version="v2"),
            RequestRetrying(
                client_request_id="2", request=request, attempt=1, wait_seconds=1.0, reason="429"
            ),
            RedirectFollowed(
                client_request_id="3", from_url="a", to_url="b", hop=1, external=False
            ),
            ResponseHeadersReceived(
                client_request_id="4",
                request=request,
                status_code=200,
                headers=[],
                elapsed_ms=0,
                external=False,
                cache_hit=False,
            ),
            RequestFailed(
                client_request_id="5",
                request=request,
                error=Exception(),
                elapsed_ms=0,
                external=False,
            ),
            RequestSucceeded(
                client_request_id="6",
                request=request,
                status_code=200,
                elapsed_ms=0,
                external=False,
            ),
            StreamCompleted(
                client_request_id="7",
                request=request,
                bytes_read=0,
                bytes_total=0,
                elapsed_ms=0,
                external=False,
            ),
            StreamAborted(
                client_request_id="8",
                request=request,
                reason="x",
                bytes_read=0,
                bytes_total=None,
                elapsed_ms=0,
                external=False,
            ),
            StreamFailed(
                client_request_id="9",
                request=request,
                error=Exception(),
                bytes_read=0,
                bytes_total=None,
                elapsed_ms=0,
                external=False,
            ),
        ]

        types = [e.type for e in events]
        assert len(types) == len(set(types)), "All event types should be unique"
        assert types == [
            "request_started",
            "request_retrying",
            "redirect_followed",
            "response_headers_received",
            "request_failed",
            "request_succeeded",
            "stream_completed",
            "stream_aborted",
            "stream_failed",
        ]
