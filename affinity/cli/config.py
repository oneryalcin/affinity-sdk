from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .errors import CLIError

if sys.version_info >= (3, 11):  # pragma: no cover
    import tomllib as _tomllib
else:  # pragma: no cover
    import tomli as _tomllib


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    api_key: str | None = None
    timeout_seconds: float | None = None
    v1_base_url: str | None = None
    v2_base_url: str | None = None


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    default: ProfileConfig
    profiles: dict[str, ProfileConfig]


def _profile_from_mapping(data: dict[str, Any]) -> ProfileConfig:
    timeout = data.get("timeout_seconds")
    return ProfileConfig(
        api_key=data.get("api_key") or None,
        timeout_seconds=float(timeout) if timeout is not None else None,
        v1_base_url=data.get("v1_base_url") or None,
        v2_base_url=data.get("v2_base_url") or None,
    )


def load_config(path: Path) -> LoadedConfig:
    if not path.exists():
        return LoadedConfig(default=ProfileConfig(), profiles={})

    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = _tomllib.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise CLIError(
            f"Invalid config file: expected a mapping at top-level: {path}",
            exit_code=2,
            error_type="usage_error",
        )

    raw_dict = cast(dict[str, Any], raw)
    default_raw_any = raw_dict.get("default")
    default_raw = default_raw_any if isinstance(default_raw_any, dict) else {}
    profiles_raw_any = raw_dict.get("profiles")
    profiles_raw = profiles_raw_any if isinstance(profiles_raw_any, dict) else {}
    profiles: dict[str, ProfileConfig] = {}
    for name, value in profiles_raw.items():
        if isinstance(value, dict):
            profiles[str(name)] = _profile_from_mapping(cast(dict[str, Any], value))

    return LoadedConfig(default=_profile_from_mapping(default_raw), profiles=profiles)


def config_file_permission_warnings(path: Path) -> list[str]:
    if os.name != "posix":
        return []
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return []

    insecure = bool(mode & (stat.S_IRGRP | stat.S_IROTH))
    if insecure:
        return [
            (
                f"Config file is group/world readable: {path} "
                "(consider `chmod 600` to protect secrets)."
            )
        ]
    return []


def config_init_template() -> str:
    return """# Affinity CLI configuration
#
# This file is optional. Prefer environment variables or --api-key-file for secrets.
# On POSIX systems, ensure permissions are restrictive (e.g. chmod 600).
#
# Format: TOML

[default]
# api_key = "..."
# timeout_seconds = 30

[profiles.dev]
# api_key = "..."
# timeout_seconds = 30
# v1_base_url = "https://api.affinity.co"
# v2_base_url = "https://api.affinity.co"
"""
