from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from affinity import Affinity
from affinity.exceptions import (
    AffinityError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from affinity.models.types import V1_BASE_URL, V2_BASE_URL

from .config import LoadedConfig, ProfileConfig, config_file_permission_warnings, load_config
from .errors import CLIError
from .paths import CliPaths, get_paths
from .results import CommandMeta, CommandResult, ErrorInfo

OutputFormat = Literal["table", "json"]


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
    log_file: Path | None
    enable_log_file: bool
    v1_base_url: str | None
    v2_base_url: str | None

    _paths: CliPaths = field(default_factory=get_paths)
    _loaded_config: LoadedConfig | None = None
    _client: Affinity | None = None

    def load_dotenv_if_requested(self) -> None:
        if not self.dotenv:
            return
        if importlib.util.find_spec("dotenv") is None:
            raise CLIError(
                "Optional .env support requires python-dotenv; install `affinity-sdk[cli]`.",
                exit_code=2,
                error_type="usage_error",
            )
        dotenv_module = importlib.import_module("dotenv")
        dotenv_module.load_dotenv(dotenv_path=self.env_file, override=False)

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

    def get_client(self, *, warnings: list[str]) -> Affinity:
        if self._client is not None:
            return self._client

        self.load_dotenv_if_requested()
        api_key = self.resolve_api_key(warnings=warnings)

        prof = self._profile_config()
        timeout = self.timeout if self.timeout is not None else prof.timeout_seconds
        if timeout is None:
            timeout = 30.0

        v1_base_url = (
            self.v1_base_url or os.getenv("AFFINITY_V1_BASE_URL") or prof.v1_base_url or V1_BASE_URL
        )
        v2_base_url = (
            self.v2_base_url or os.getenv("AFFINITY_V2_BASE_URL") or prof.v2_base_url or V2_BASE_URL
        )

        self._client = Affinity(
            api_key=api_key,
            v1_base_url=v1_base_url,
            v2_base_url=v2_base_url,
            timeout=timeout,
            log_requests=self.verbosity >= 2,
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
