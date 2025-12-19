from __future__ import annotations

import os
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from affinity import Affinity
from affinity.client import _maybe_load_dotenv as _sdk_maybe_load_dotenv
from affinity.exceptions import (
    AffinityError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from affinity.hooks import ErrorHook, RequestHook, ResponseHook
from affinity.models.types import V1_BASE_URL, V2_BASE_URL
from affinity.policies import Policies, WritePolicy

from .config import LoadedConfig, ProfileConfig, config_file_permission_warnings, load_config
from .errors import CLIError
from .logging import set_redaction_api_key
from .paths import CliPaths, get_paths
from .results import CommandMeta, CommandResult, ErrorInfo

OutputFormat = Literal["table", "json"]

_CLI_CACHE_ENABLED = True
_CLI_CACHE_TTL_SECONDS = 300.0


def _strip_url_query_and_fragment(url: str) -> str:
    """
    Keep scheme/host/path but drop query/fragment to reduce accidental leakage of PII/filters.
    """
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return url


@dataclass(frozen=True, slots=True)
class ClientSettings:
    api_key: str
    timeout: float
    v1_base_url: str
    v2_base_url: str
    log_requests: bool
    max_retries: int
    policies: Policies
    on_request: RequestHook | None
    on_response: ResponseHook | None
    on_error: ErrorHook | None


@dataclass
class CLIContext:
    output: OutputFormat
    quiet: bool
    verbosity: int
    pager: bool | None
    progress: Literal["auto", "always", "never"]
    profile: str | None
    dotenv: bool
    env_file: Path
    api_key_file: str | None
    api_key_stdin: bool
    timeout: float | None
    max_retries: int
    readonly: bool
    trace: bool
    log_file: Path | None
    enable_log_file: bool
    v1_base_url: str | None
    v2_base_url: str | None

    _paths: CliPaths = field(default_factory=get_paths)
    _loaded_config: LoadedConfig | None = None
    _client: Affinity | None = None

    def load_dotenv_if_requested(self) -> None:
        try:
            _sdk_maybe_load_dotenv(
                load_dotenv=self.dotenv,
                dotenv_path=self.env_file,
                override=False,
            )
        except ImportError as exc:
            raise CLIError(
                "Optional .env support requires python-dotenv; install `affinity-sdk[cli]`.",
                exit_code=2,
                error_type="usage_error",
            ) from exc

    @property
    def paths(self) -> CliPaths:
        return self._paths

    def _config_path(self) -> Path:
        return self.paths.config_path

    def load_config(self) -> LoadedConfig:
        if self._loaded_config is None:
            self._loaded_config = load_config(self._config_path())
        return self._loaded_config

    def _effective_profile(self) -> str:
        return self.profile or os.getenv("AFFINITY_PROFILE") or "default"

    def _profile_config(self) -> ProfileConfig:
        cfg = self.load_config()
        if self._effective_profile() == "default":
            return cfg.default
        return cfg.profiles.get(self._effective_profile(), ProfileConfig())

    def resolve_api_key(self, *, warnings: list[str]) -> str:
        if self.api_key_stdin:
            raw = sys.stdin.read()
            key = raw.strip()
            if not key:
                raise CLIError(
                    "Empty API key provided via stdin.", exit_code=2, error_type="usage_error"
                )
            return key

        if self.api_key_file is not None:
            if self.api_key_file == "-":
                raw = sys.stdin.read()
                key = raw.strip()
                if not key:
                    raise CLIError(
                        "Empty API key provided via stdin.", exit_code=2, error_type="usage_error"
                    )
                return key
            path = Path(self.api_key_file)
            key = path.read_text(encoding="utf-8").strip()
            if not key:
                raise CLIError(f"Empty API key file: {path}", exit_code=2, error_type="usage_error")
            return key

        env_key = os.getenv("AFFINITY_API_KEY", "").strip()
        if env_key:
            return env_key

        prof = self._profile_config()
        if prof.api_key:
            warnings.extend(config_file_permission_warnings(self._config_path()))
            return prof.api_key.strip()

        raise CLIError(
            (
                "Missing API key. Set AFFINITY_API_KEY, use --api-key-file/--api-key-stdin, "
                "or configure profiles."
            ),
            exit_code=2,
            error_type="usage_error",
        )

    def resolve_client_settings(self, *, warnings: list[str]) -> ClientSettings:
        self.load_dotenv_if_requested()
        api_key = self.resolve_api_key(warnings=warnings)
        set_redaction_api_key(api_key)

        prof = self._profile_config()
        timeout = self.timeout if self.timeout is not None else prof.timeout_seconds
        if timeout is None:
            timeout = 30.0
        if self.max_retries < 0:
            raise CLIError("--max-retries must be >= 0.", exit_code=2, error_type="usage_error")

        v1_base_url = (
            self.v1_base_url or os.getenv("AFFINITY_V1_BASE_URL") or prof.v1_base_url or V1_BASE_URL
        )
        v2_base_url = (
            self.v2_base_url or os.getenv("AFFINITY_V2_BASE_URL") or prof.v2_base_url or V2_BASE_URL
        )

        on_request: RequestHook | None = None
        on_response: ResponseHook | None = None
        on_error: ErrorHook | None = None
        if self.trace:

            def _write(line: str) -> None:
                sys.stderr.write(line + "\n")
                with suppress(Exception):
                    sys.stderr.flush()

            def _on_request(req: Any) -> None:
                method = str(getattr(req, "method", "?"))
                url = _strip_url_query_and_fragment(str(getattr(req, "url", "?")))
                _write(f"trace -> {method} {url}")

            def _on_response(res: Any) -> None:
                status = str(getattr(res, "status_code", "?"))
                elapsed = getattr(res, "elapsed_ms", None)
                cache_hit = bool(getattr(res, "cache_hit", False))
                req = getattr(res, "request", None)
                url = getattr(req, "url", "?") if req is not None else "?"
                url = _strip_url_query_and_fragment(str(url))
                extra = []
                if elapsed is not None:
                    extra.append(f"elapsedMs={int(elapsed)}")
                if cache_hit:
                    extra.append("cacheHit=true")
                suffix = (" " + " ".join(extra)) if extra else ""
                _write(f"trace <- {status} {url}{suffix}")

            def _on_error(err: Any) -> None:
                req = getattr(err, "request", None)
                url = getattr(req, "url", "?") if req is not None else "?"
                url = _strip_url_query_and_fragment(str(url))
                exc = getattr(err, "error", None)
                exc_name = type(exc).__name__ if exc is not None else "Error"
                _write(f"trace !! {exc_name} {url}")

            on_request = _on_request
            on_response = _on_response
            on_error = _on_error

        policies = Policies(write=WritePolicy.DENY) if self.readonly else Policies()

        return ClientSettings(
            api_key=api_key,
            timeout=timeout,
            v1_base_url=v1_base_url,
            v2_base_url=v2_base_url,
            log_requests=self.verbosity >= 2,
            max_retries=self.max_retries,
            policies=policies,
            on_request=on_request,
            on_response=on_response,
            on_error=on_error,
        )

    def get_client(self, *, warnings: list[str]) -> Affinity:
        if self._client is not None:
            return self._client

        settings = self.resolve_client_settings(warnings=warnings)

        self._client = Affinity(
            api_key=settings.api_key,
            v1_base_url=settings.v1_base_url,
            v2_base_url=settings.v2_base_url,
            timeout=settings.timeout,
            log_requests=settings.log_requests,
            max_retries=settings.max_retries,
            enable_cache=_CLI_CACHE_ENABLED,
            cache_ttl=_CLI_CACHE_TTL_SECONDS,
            on_request=settings.on_request,
            on_response=settings.on_response,
            on_error=settings.on_error,
            policies=settings.policies,
        )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def exit_code_for_exception(exc: Exception) -> int:
    if isinstance(exc, CLIError):
        return exc.exit_code
    if isinstance(exc, (AuthenticationError, AuthorizationError)):
        return 3
    if isinstance(exc, NotFoundError):
        return 4
    if isinstance(exc, (RateLimitError, ServerError)):
        return 5
    if isinstance(exc, AffinityError):
        return 1
    return 1


def error_info_for_exception(exc: Exception) -> ErrorInfo:
    if isinstance(exc, CLIError):
        return ErrorInfo(type=exc.error_type, message=exc.message, details=exc.details)
    if isinstance(exc, AffinityError):
        return ErrorInfo(type=exc.__class__.__name__, message=str(exc), details=None)
    return ErrorInfo(type=exc.__class__.__name__, message=str(exc), details=None)


def build_result(
    *,
    ok: bool,
    command: str,
    started_at: float,
    data: Any | None,
    artifacts: list[Any] | None = None,
    warnings: list[str],
    profile: str | None,
    rate_limit: Any | None,
    pagination: dict[str, Any] | None = None,
    resolved: dict[str, Any] | None = None,
    columns: list[dict[str, Any]] | None = None,
    error: ErrorInfo | None = None,
) -> CommandResult:
    duration_ms = int(max(0.0, (time.time() - started_at) * 1000))
    meta = CommandMeta(
        duration_ms=duration_ms,
        profile=profile,
        pagination=pagination,
        resolved=resolved,
        columns=columns,
        rate_limit=rate_limit,
    )
    return CommandResult(
        ok=ok,
        command=command,
        data=data,
        artifacts=artifacts or [],
        warnings=warnings,
        meta=meta,
        error=error,
    )
