"""
Custom exceptions for the Affinity API client.

All exceptions inherit from AffinityError for easy catching of all library errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorDiagnostics:
    method: str | None = None
    url: str | None = None
    api_version: str | None = None  # "v1" | "v2" (string to avoid circular types)
    base_url: str | None = None
    request_id: str | None = None
    http_version: str | None = None
    response_headers: dict[str, str] | None = None
    response_body_snippet: str | None = None


class AffinityError(Exception):
    """Base exception for all Affinity API errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: Any | None = None,
        diagnostics: ErrorDiagnostics | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.diagnostics = diagnostics

    def __str__(self) -> str:
        base = self.message
        if self.status_code:
            base = f"[{self.status_code}] {base}"
        if self.diagnostics and self.diagnostics.method and self.diagnostics.url:
            base = f"{base} ({self.diagnostics.method} {self.diagnostics.url})"
        if self.diagnostics and self.diagnostics.request_id:
            base = f"{base} [request_id={self.diagnostics.request_id}]"
        return base


# =============================================================================
# HTTP Errors
# =============================================================================


class AuthenticationError(AffinityError):
    """
    401 Unauthorized - Invalid or missing API key.

    Your API key is invalid or was not provided.
    """

    pass


class AuthorizationError(AffinityError):
    """
    403 Forbidden - Insufficient permissions.

    You don't have permission to access this resource or perform this action.
    This can happen with:
    - Private lists you don't have access to
    - Admin-only actions
    - Resource-level permission restrictions
    """

    pass


class NotFoundError(AffinityError):
    """
    404 Not Found - Resource doesn't exist.

    The requested resource (person, company, list, etc.) was not found.
    This could mean:
    - The ID is invalid
    - The resource was deleted
    - You don't have access to view it
    """

    pass


class ValidationError(AffinityError):
    """
    400/422 Bad Request/Unprocessable Entity - Invalid request data.

    The request data is malformed or logically invalid.
    Check the error message for details about what's wrong.
    """

    def __init__(
        self,
        message: str,
        *,
        param: str | None = None,
        status_code: int | None = None,
        response_body: Any | None = None,
        diagnostics: ErrorDiagnostics | None = None,
    ):
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            diagnostics=diagnostics,
        )
        self.param = param

    def __str__(self) -> str:
        base = super().__str__()
        if self.param:
            return f"{base} (param: {self.param})"
        return base


class RateLimitError(AffinityError):
    """
    429 Too Many Requests - Rate limit exceeded.

    You've exceeded the API rate limit. Wait before retrying.
    Check the response headers for rate limit info:
    - X-Ratelimit-Limit-User-Reset: Seconds until per-minute limit resets
    - X-Ratelimit-Limit-Org-Reset: Seconds until monthly limit resets
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: int | None = None,
        status_code: int | None = None,
        response_body: Any | None = None,
        diagnostics: ErrorDiagnostics | None = None,
    ):
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            diagnostics=diagnostics,
        )
        self.retry_after = retry_after


class ConflictError(AffinityError):
    """
    409 Conflict - Resource conflict.

    The request conflicts with the current state of the resource.
    For example:
    - Trying to create a person with an email that already exists
    - Concurrent modification conflicts
    """

    pass


class ServerError(AffinityError):
    """
    500/503 Internal Server Error - Server-side problem.

    Something went wrong on Affinity's servers.
    Try again later, and contact support if the problem persists.
    """

    pass


# =============================================================================
# Client-side Errors
# =============================================================================


class ConfigurationError(AffinityError):
    """
    Configuration error - missing or invalid client configuration.

    Check that you've provided:
    - A valid API key
    - Correct base URLs (if customizing)
    """

    pass


class TimeoutError(AffinityError):
    """
    Request timeout.

    The request took too long to complete.
    This could be due to:
    - Network issues
    - Large data sets
    - Server overload
    """

    pass


class NetworkError(AffinityError):
    """
    Network-level error.

    Failed to connect to the Affinity API.
    Check your internet connection and firewall settings.
    """

    pass


# =============================================================================
# URL Safety Errors
# =============================================================================


class UnsafeUrlError(AffinityError):
    """
    SDK blocked following a server-provided URL.

    Raised when SafeFollowUrl policy rejects a URL (scheme/host/userinfo/redirect).
    """

    def __init__(self, message: str, *, url: str | None = None):
        super().__init__(message)
        self.url = url


# =============================================================================
# Business Logic Errors
# =============================================================================


class EntityNotFoundError(NotFoundError):
    """
    Specific entity not found.

    Provides type-safe context about which entity type was not found.
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: int | str,
        **kwargs: Any,
    ):
        message = f"{entity_type} with ID {entity_id} not found"
        super().__init__(message, **kwargs)
        self.entity_type = entity_type
        self.entity_id = entity_id


class FieldNotFoundError(NotFoundError):
    """Field with the specified ID was not found."""

    pass


class ListNotFoundError(NotFoundError):
    """List with the specified ID was not found."""

    pass


class PersonNotFoundError(EntityNotFoundError):
    """Person with the specified ID was not found."""

    def __init__(self, person_id: int, **kwargs: Any):
        super().__init__("Person", person_id, **kwargs)


class CompanyNotFoundError(EntityNotFoundError):
    """Company with the specified ID was not found."""

    def __init__(self, company_id: int, **kwargs: Any):
        super().__init__("Company", company_id, **kwargs)


class OpportunityNotFoundError(EntityNotFoundError):
    """Opportunity with the specified ID was not found."""

    def __init__(self, opportunity_id: int, **kwargs: Any):
        super().__init__("Opportunity", opportunity_id, **kwargs)


# =============================================================================
# API Version Errors
# =============================================================================


class UnsupportedOperationError(AffinityError):
    """
    Operation not supported by the current API version.

    Some operations are only available in V1 or V2.
    """

    pass


class BetaEndpointDisabledError(UnsupportedOperationError):
    """Attempted to call a beta endpoint without opt-in."""

    pass


class VersionCompatibilityError(AffinityError):
    """
    Response shape mismatch suggests API version incompatibility.

    TR-015: Raised when the SDK detects response-shape mismatches that
    appear version-related. This typically means the API key's configured
    v2 Default API Version differs from what the SDK expects.

    Guidance:
    1. Check your API key's v2 Default API Version in the Affinity dashboard
    2. Ensure it matches the expected_v2_version configured in the SDK
    3. See: https://developer.affinity.co/#section/Getting-Started/Versioning
    """

    def __init__(
        self,
        message: str,
        *,
        expected_version: str | None = None,
        parsing_error: str | None = None,
        status_code: int | None = None,
        response_body: Any | None = None,
        diagnostics: ErrorDiagnostics | None = None,
    ):
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            diagnostics=diagnostics,
        )
        self.expected_version = expected_version
        self.parsing_error = parsing_error

    def __str__(self) -> str:
        base = super().__str__()
        hints = []
        if self.expected_version:
            hints.append(f"expected_v2_version={self.expected_version}")
        if self.parsing_error:
            hints.append(f"parsing_error={self.parsing_error}")
        if hints:
            base = f"{base} ({', '.join(hints)})"
        return base


class DeprecationWarning(AffinityError):
    """
    Feature is deprecated and may be removed.
    """

    pass


# =============================================================================
# Error Factory
# =============================================================================


def error_from_response(
    status_code: int,
    response_body: Any,
    *,
    retry_after: int | None = None,
    diagnostics: ErrorDiagnostics | None = None,
) -> AffinityError:
    """
    Create the appropriate exception from an API error response.

    Args:
        status_code: HTTP status code
        response_body: Parsed response body (usually dict with 'errors')
        retry_after: Retry-After header value for rate limits

    Returns:
        Appropriate AffinityError subclass
    """
    # Try to extract message from response
    message = "Unknown error"
    param = None

    if isinstance(response_body, dict):
        errors = response_body.get("errors", [])
        if errors and isinstance(errors, list) and len(errors) > 0:
            first_error = errors[0]
            if isinstance(first_error, dict):
                message = first_error.get("message", message)
                param = first_error.get("param")

    # Map status codes to exceptions
    error_mapping: dict[int, type[AffinityError]] = {
        400: ValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        409: ConflictError,
        422: ValidationError,
        429: RateLimitError,
        500: ServerError,
        503: ServerError,
    }

    error_class = error_mapping.get(status_code, AffinityError)

    # Special handling for ValidationError with param
    if error_class is ValidationError:
        return ValidationError(
            message,
            param=param,
            status_code=status_code,
            response_body=response_body,
            diagnostics=diagnostics,
        )

    # Special handling for RateLimitError with retry_after
    if error_class is RateLimitError:
        return RateLimitError(
            message,
            retry_after=retry_after,
            status_code=status_code,
            response_body=response_body,
            diagnostics=diagnostics,
        )

    return error_class(
        message,
        status_code=status_code,
        response_body=response_body,
        diagnostics=diagnostics,
    )
