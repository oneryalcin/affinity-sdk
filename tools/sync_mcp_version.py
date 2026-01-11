#!/usr/bin/env python3
"""Sync version from mcp/VERSION to MCP plugin and server metadata files.

This script syncs the MCP version to:
- mcp/.claude-plugin/plugin.json
- mcp/server.d/server.meta.json

The single source of truth is mcp/VERSION.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Files that should match mcp/VERSION
MCP_VERSION_TARGETS = [
    "mcp/.claude-plugin/plugin.json",
    "mcp/server.d/server.meta.json",
]


def main() -> int:
    """Sync version and exit with 1 if files were modified."""
    root = Path(__file__).parent.parent
    modified = False

    # Read version from mcp/VERSION
    version_path = root / "mcp" / "VERSION"
    if not version_path.exists():
        print("Error: mcp/VERSION not found")
        return 1

    mcp_version = version_path.read_text().strip()

    # Update each target file
    for rel_path in MCP_VERSION_TARGETS:
        target_path = root / rel_path
        if not target_path.exists():
            print(f"Warning: {rel_path} not found, skipping")
            continue

        with target_path.open() as f:
            data = json.load(f)

        if data.get("version") == mcp_version:
            continue  # Already in sync

        # Update version
        data["version"] = mcp_version
        with target_path.open("w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

        print(f"Updated {rel_path} version to {mcp_version}")
        modified = True

    return 1 if modified else 0


if __name__ == "__main__":
    sys.exit(main())
