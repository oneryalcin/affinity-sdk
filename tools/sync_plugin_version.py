#!/usr/bin/env python3
"""Sync version from pyproject.toml to .claude-plugin/plugin.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


def main() -> int:
    """Sync version and exit with 1 if files were modified."""
    root = Path(__file__).parent.parent

    # Read version from pyproject.toml
    pyproject_path = root / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    sdk_version = pyproject["project"]["version"]

    # Read and update plugin.json
    plugin_json_path = root / ".claude-plugin" / "plugin.json"
    if not plugin_json_path.exists():
        return 0  # No plugin.json, nothing to sync

    with plugin_json_path.open() as f:
        plugin_data = json.load(f)

    if plugin_data.get("version") == sdk_version:
        return 0  # Already in sync

    # Update version
    plugin_data["version"] = sdk_version
    with plugin_json_path.open("w") as f:
        json.dump(plugin_data, f, indent=2)
        f.write("\n")

    print(f"Updated .claude-plugin/plugin.json version to {sdk_version}")
    return 1  # Files were modified


if __name__ == "__main__":
    sys.exit(main())
