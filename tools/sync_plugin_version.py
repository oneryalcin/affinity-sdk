#!/usr/bin/env python3
"""Sync version from pyproject.toml to plugin.json files.

This script syncs the SDK version to:
- plugins/affinity-sdk/.claude-plugin/plugin.json
- plugins/xaffinity-cli/.claude-plugin/plugin.json

Note: MCP plugin (mcp/.claude-plugin/plugin.json) is NOT synced as it has
independent versioning. See docs/internal/versioning-strategy.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

# Plugin paths that should match SDK version
# MCP plugin is intentionally excluded - it has independent versioning
PLUGIN_PATHS = [
    ".claude-plugin/plugin.json",  # Root (if exists)
    "plugins/affinity-sdk/.claude-plugin/plugin.json",
    "plugins/xaffinity-cli/.claude-plugin/plugin.json",
]


def main() -> int:
    """Sync version and exit with 1 if files were modified."""
    root = Path(__file__).parent.parent
    modified = False

    # Read version from pyproject.toml
    pyproject_path = root / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    sdk_version = pyproject["project"]["version"]

    # Update each plugin.json
    for rel_path in PLUGIN_PATHS:
        plugin_json_path = root / rel_path
        if not plugin_json_path.exists():
            print(f"Warning: {rel_path} not found, skipping")
            continue

        with plugin_json_path.open() as f:
            plugin_data = json.load(f)

        if plugin_data.get("version") == sdk_version:
            continue  # Already in sync

        # Update version
        plugin_data["version"] = sdk_version
        with plugin_json_path.open("w") as f:
            json.dump(plugin_data, f, indent=2)
            f.write("\n")

        print(f"Updated {rel_path} version to {sdk_version}")
        modified = True

    return 1 if modified else 0


if __name__ == "__main__":
    sys.exit(main())
