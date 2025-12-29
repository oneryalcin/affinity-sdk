from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs


@dataclass(frozen=True, slots=True)
class CliPaths:
    config_dir: Path
    config_path: Path
    cache_dir: Path
    state_dir: Path
    log_dir: Path
    log_file: Path


def get_paths(*, app_name: str = "xaffinity", app_author: str = "Affinity") -> CliPaths:
    dirs = PlatformDirs(app_name, app_author)
    config_dir = Path(dirs.user_config_dir)
    cache_dir = Path(dirs.user_cache_dir)
    state_dir = Path(dirs.user_state_dir)
    log_dir = Path(getattr(dirs, "user_log_dir", "") or (state_dir / "logs"))
    return CliPaths(
        config_dir=config_dir,
        config_path=config_dir / "config.toml",
        cache_dir=cache_dir,
        state_dir=state_dir,
        log_dir=log_dir,
        log_file=log_dir / "xaffinity.log",
    )
