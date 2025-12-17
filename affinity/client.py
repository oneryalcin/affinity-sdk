"""
Main Affinity API client.

Provides a unified interface to all Affinity API functionality.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
from typing import Any, Literal, cast

from .clients.http import (
    AsyncHTTPClient,
    ClientConfig,
    HTTPClient,
    RequestHook,
    ResponseHook,
)
from .models.types import V1_BASE_URL, V2_BASE_URL
from .services.companies import AsyncCompanyService, CompanyService
from .services.lists import AsyncListService, ListService
from .services.opportunities import AsyncOpportunityService, OpportunityService
from .services.persons import AsyncPersonService, PersonService
from .services.tasks import AsyncTaskService, TaskService
from .services.v1_only import (
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

_DEFAULT_API_KEY_ENV_VAR = "AFFINITY_API_KEY"


def _maybe_load_dotenv(
    *,
    load_dotenv: bool,
    dotenv_path: str | os.PathLike[str] | None,
    override: bool,
) -> None:
    if not load_dotenv:
        return

    if importlib.util.find_spec("dotenv") is None:
        raise ImportError(
            "Optional .env support requires python-dotenv; install `affinity-sdk[dotenv]` "
            "or `python-dotenv`."
        )

    dotenv_module = cast(Any, importlib.import_module("dotenv"))
    dotenv_module.load_dotenv(dotenv_path=dotenv_path, override=override)


def _api_key_from_env(
    *,
    env_var: str,
    load_dotenv: bool,
    dotenv_path: str | os.PathLike[str] | None,
    dotenv_override: bool,
) -> str:
    _maybe_load_dotenv(load_dotenv=load_dotenv, dotenv_path=dotenv_path, override=dotenv_override)
    api_key = os.getenv(env_var, "").strip()
    if not api_key:
        raise ValueError(
            f"Missing API key: set `{env_var}` or initialize the client with `api_key=...`."
        )
    return api_key


class Affinity:
    """
    Synchronous Affinity API client.

    Provides access to all Affinity API functionality with a clean,
    Pythonic interface. Uses V2 API where available, falls back to V1
    for operations not yet supported in V2.

    Example:
        ```python
        from affinity import Affinity

        # Initialize with API key
        client = Affinity(api_key="your-api-key")

        # Use as context manager for automatic cleanup
        with Affinity(api_key="your-api-key") as client:
            # Get all companies
            for company in client.companies.all():
                print(company.name)

            # Get a specific person with field data
            person = client.persons.get(
                PersonId(12345),
                field_types=["enriched", "global"]
            )

            # Add a company to a list
            entries = client.lists.entries(ListId(789))
            entry = entries.add_company(CompanyId(456))

            # Update field values
            entries.update_field_value(
                entry.id,
                FieldId(101),
                "New value"
            )
        ```

    Attributes:
        companies: Company (organization) operations
        persons: Person (contact) operations
        lists: List operations
        notes: Note operations
        reminders: Reminder operations
        webhooks: Webhook subscription operations
        interactions: Interaction (email, meeting, etc.) operations
        fields: Custom field operations
        field_values: Field value operations
        files: Entity file operations
        relationships: Relationship strength queries
        auth: Authentication and rate limit info
    """

    def __init__(
        self,
        api_key: str,
        *,
        v1_base_url: str = V1_BASE_URL,
        v2_base_url: str = V2_BASE_URL,
        v1_auth_mode: Literal["bearer", "basic"] = "bearer",
        enable_beta_endpoints: bool = False,
        allow_insecure_download_redirects: bool = False,
        expected_v2_version: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        enable_cache: bool = False,
        cache_ttl: float = 300.0,
        log_requests: bool = False,
        on_request: RequestHook | None = None,
        on_response: ResponseHook | None = None,
    ):
        """
        Initialize the Affinity client.

        Args:
            api_key: Your Affinity API key
            v1_base_url: V1 API base URL (default: https://api.affinity.co)
            v2_base_url: V2 API base URL (default: https://api.affinity.co/v2)
            v1_auth_mode: Auth mode for V1 API ("bearer" or "basic")
            enable_beta_endpoints: Enable beta V2 endpoints
            allow_insecure_download_redirects: Allow `http://` redirects for file downloads.
                Not recommended; prefer HTTPS-only downloads.
            expected_v2_version: Expected V2 API version for diagnostics (e.g.,
                "2024-01-01"). Used to detect version compatibility issues.
                See TR-015.
            timeout: Request timeout in seconds
            max_retries: Maximum retries for rate-limited requests
            enable_cache: Enable response caching for field metadata
            cache_ttl: Cache TTL in seconds
            log_requests: Log all HTTP requests (for debugging)
            on_request: Hook called before each request (DX-008)
            on_response: Hook called after each response (DX-008)
        """
        config = ClientConfig(
            api_key=api_key,
            v1_base_url=v1_base_url,
            v2_base_url=v2_base_url,
            v1_auth_mode=v1_auth_mode,
            enable_beta_endpoints=enable_beta_endpoints,
            allow_insecure_download_redirects=allow_insecure_download_redirects,
            expected_v2_version=expected_v2_version,
            timeout=timeout,
            max_retries=max_retries,
            enable_cache=enable_cache,
            cache_ttl=cache_ttl,
            log_requests=log_requests,
            on_request=on_request,
            on_response=on_response,
        )
        self._http = HTTPClient(config)

        # Initialize services
        self._companies: CompanyService | None = None
        self._persons: PersonService | None = None
        self._lists: ListService | None = None
        self._opportunities: OpportunityService | None = None
        self._tasks: TaskService | None = None
        self._notes: NoteService | None = None
        self._reminders: ReminderService | None = None
        self._webhooks: WebhookService | None = None
        self._interactions: InteractionService | None = None
        self._fields: FieldService | None = None
        self._field_values: FieldValueService | None = None
        self._files: EntityFileService | None = None
        self._relationships: RelationshipStrengthService | None = None
        self._auth: AuthService | None = None

    @classmethod
    def from_env(
        cls,
        *,
        env_var: str = _DEFAULT_API_KEY_ENV_VAR,
        load_dotenv: bool = False,
        dotenv_path: str | os.PathLike[str] | None = None,
        dotenv_override: bool = False,
        **kwargs: Any,
    ) -> Affinity:
        """
        Create a client using an API key from the environment.

        By default, reads `AFFINITY_API_KEY`. For local development, you can optionally
        load a `.env` file (requires `python-dotenv`).
        """
        api_key = _api_key_from_env(
            env_var=env_var,
            load_dotenv=load_dotenv,
            dotenv_path=dotenv_path,
            dotenv_override=dotenv_override,
        )
        return cls(api_key=api_key, **kwargs)

    def __enter__(self) -> Affinity:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._http.close()

    # =========================================================================
    # Service Properties (lazy initialization)
    # =========================================================================

    @property
    def companies(self) -> CompanyService:
        """Company (organization) operations."""
        if self._companies is None:
            self._companies = CompanyService(self._http)
        return self._companies

    @property
    def persons(self) -> PersonService:
        """Person (contact) operations."""
        if self._persons is None:
            self._persons = PersonService(self._http)
        return self._persons

    @property
    def lists(self) -> ListService:
        """List operations."""
        if self._lists is None:
            self._lists = ListService(self._http)
        return self._lists

    @property
    def opportunities(self) -> OpportunityService:
        """Opportunity operations."""
        if self._opportunities is None:
            self._opportunities = OpportunityService(self._http)
        return self._opportunities

    @property
    def tasks(self) -> TaskService:
        """Long-running task operations (polling, waiting)."""
        if self._tasks is None:
            self._tasks = TaskService(self._http)
        return self._tasks

    @property
    def notes(self) -> NoteService:
        """Note operations."""
        if self._notes is None:
            self._notes = NoteService(self._http)
        return self._notes

    @property
    def reminders(self) -> ReminderService:
        """Reminder operations."""
        if self._reminders is None:
            self._reminders = ReminderService(self._http)
        return self._reminders

    @property
    def webhooks(self) -> WebhookService:
        """Webhook subscription operations."""
        if self._webhooks is None:
            self._webhooks = WebhookService(self._http)
        return self._webhooks

    @property
    def interactions(self) -> InteractionService:
        """Interaction operations."""
        if self._interactions is None:
            self._interactions = InteractionService(self._http)
        return self._interactions

    @property
    def fields(self) -> FieldService:
        """Custom field operations."""
        if self._fields is None:
            self._fields = FieldService(self._http)
        return self._fields

    @property
    def field_values(self) -> FieldValueService:
        """Field value operations."""
        if self._field_values is None:
            self._field_values = FieldValueService(self._http)
        return self._field_values

    @property
    def files(self) -> EntityFileService:
        """Entity file operations."""
        if self._files is None:
            self._files = EntityFileService(self._http)
        return self._files

    @property
    def relationships(self) -> RelationshipStrengthService:
        """Relationship strength queries."""
        if self._relationships is None:
            self._relationships = RelationshipStrengthService(self._http)
        return self._relationships

    @property
    def auth(self) -> AuthService:
        """Authentication and rate limit info."""
        if self._auth is None:
            self._auth = AuthService(self._http)
        return self._auth

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._http.cache:
            self._http.cache.clear()

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        """Get the current rate limit state tracked by the client."""
        state = self._http.rate_limit_state
        return {
            "user_limit": state.user_limit,
            "user_remaining": state.user_remaining,
            "user_reset_seconds": state.user_reset_seconds,
            "org_limit": state.org_limit,
            "org_remaining": state.org_remaining,
            "org_reset_seconds": state.org_reset_seconds,
        }


# =============================================================================
# Async Client (same interface, async methods)
# =============================================================================

# The async client mirrors the sync client interface for core services (TR-009).


class AsyncAffinity:
    """
    Asynchronous Affinity API client.

    Same interface as Affinity but with async/await support.

    Example:
        ```python
        async with AsyncAffinity(api_key="your-key") as client:
            async for company in client.companies.all():
                print(company.name)
        ```
    """

    def __init__(
        self,
        api_key: str,
        *,
        v1_base_url: str = V1_BASE_URL,
        v2_base_url: str = V2_BASE_URL,
        v1_auth_mode: Literal["bearer", "basic"] = "bearer",
        enable_beta_endpoints: bool = False,
        allow_insecure_download_redirects: bool = False,
        expected_v2_version: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        enable_cache: bool = False,
        cache_ttl: float = 300.0,
        log_requests: bool = False,
        on_request: RequestHook | None = None,
        on_response: ResponseHook | None = None,
    ):
        """
        Initialize the async Affinity client.

        Args:
            api_key: Your Affinity API key
            v1_base_url: V1 API base URL (default: https://api.affinity.co)
            v2_base_url: V2 API base URL (default: https://api.affinity.co/v2)
            v1_auth_mode: Auth mode for V1 API ("bearer" or "basic")
            enable_beta_endpoints: Enable beta V2 endpoints
            allow_insecure_download_redirects: Allow `http://` redirects for file downloads.
                Not recommended; prefer HTTPS-only downloads.
            expected_v2_version: Expected V2 API version for diagnostics (e.g.,
                "2024-01-01"). Used to detect version compatibility issues.
                See TR-015.
            timeout: Request timeout in seconds
            max_retries: Maximum retries for rate-limited requests
            enable_cache: Enable response caching for field metadata
            cache_ttl: Cache TTL in seconds
            log_requests: Log all HTTP requests (for debugging)
            on_request: Hook called before each request (DX-008)
            on_response: Hook called after each response (DX-008)
        """
        config = ClientConfig(
            api_key=api_key,
            v1_base_url=v1_base_url,
            v2_base_url=v2_base_url,
            v1_auth_mode=v1_auth_mode,
            enable_beta_endpoints=enable_beta_endpoints,
            allow_insecure_download_redirects=allow_insecure_download_redirects,
            expected_v2_version=expected_v2_version,
            timeout=timeout,
            max_retries=max_retries,
            enable_cache=enable_cache,
            cache_ttl=cache_ttl,
            log_requests=log_requests,
            on_request=on_request,
            on_response=on_response,
        )
        self._http = AsyncHTTPClient(config)
        self._companies: AsyncCompanyService | None = None
        self._persons: AsyncPersonService | None = None
        self._opportunities: AsyncOpportunityService | None = None
        self._lists: AsyncListService | None = None
        self._tasks: AsyncTaskService | None = None

    @classmethod
    def from_env(
        cls,
        *,
        env_var: str = _DEFAULT_API_KEY_ENV_VAR,
        load_dotenv: bool = False,
        dotenv_path: str | os.PathLike[str] | None = None,
        dotenv_override: bool = False,
        **kwargs: Any,
    ) -> AsyncAffinity:
        """
        Create an async client using an API key from the environment.

        By default, reads `AFFINITY_API_KEY`. For local development, you can optionally
        load a `.env` file (requires `python-dotenv`).
        """
        api_key = _api_key_from_env(
            env_var=env_var,
            load_dotenv=load_dotenv,
            dotenv_path=dotenv_path,
            dotenv_override=dotenv_override,
        )
        return cls(api_key=api_key, **kwargs)

    @property
    def companies(self) -> AsyncCompanyService:
        """Company (organization) operations."""
        if self._companies is None:
            self._companies = AsyncCompanyService(self._http)
        return self._companies

    @property
    def persons(self) -> AsyncPersonService:
        """Person (contact) operations."""
        if self._persons is None:
            self._persons = AsyncPersonService(self._http)
        return self._persons

    @property
    def opportunities(self) -> AsyncOpportunityService:
        """Opportunity operations."""
        if self._opportunities is None:
            self._opportunities = AsyncOpportunityService(self._http)
        return self._opportunities

    @property
    def lists(self) -> AsyncListService:
        """List and list entry operations."""
        if self._lists is None:
            self._lists = AsyncListService(self._http)
        return self._lists

    @property
    def tasks(self) -> AsyncTaskService:
        """Long-running task operations (polling, waiting)."""
        if self._tasks is None:
            self._tasks = AsyncTaskService(self._http)
        return self._tasks

    async def __aenter__(self) -> AsyncAffinity:
        """Enter an async context and return this client."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit the async context and close the underlying HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.close()
