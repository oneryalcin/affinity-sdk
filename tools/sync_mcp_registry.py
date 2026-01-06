#!/usr/bin/env python3
"""Sync MCP CLI commands registry with current CLI version.

This pre-commit hook regenerates mcp/server.d/registry/commands.json when
pyproject.toml changes (indicating a version bump). This ensures the registry
stays in sync with the CLI version.

The hook:
1. Reads the current registry's cliVersion
2. Gets the installed CLI version
3. If different, regenerates the registry
4. Returns exit code 1 if files were modified (pre-commit re-stages)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def get_installed_cli_version() -> str | None:
    """Get xaffinity CLI version from installed package."""
    try:
        result = subprocess.run(
            ["xaffinity", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Output format: "xaffinity, version 0.6.9"
        return result.stdout.strip().split()[-1]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_registry_cli_version(registry_path: Path) -> str | None:
    """Get CLI version from existing registry file."""
    if not registry_path.exists():
        return None
    try:
        data = json.loads(registry_path.read_text())
        return data.get("cliVersion")
    except (json.JSONDecodeError, OSError):
        return None


def regenerate_registry() -> bool:
    """Regenerate the registry using the generator script.

    Returns True if successful, False otherwise.
    """
    repo_root = Path(__file__).parent.parent
    generator = repo_root / "tools" / "generate_cli_commands_registry.py"

    try:
        subprocess.run(
            [sys.executable, str(generator)],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error regenerating registry: {e.stderr}", file=sys.stderr)
        return False


def main() -> int:
    """Check and sync registry if needed. Returns 1 if modified."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "mcp" / "server.d" / "registry" / "commands.json"

    # Get versions
    installed_version = get_installed_cli_version()
    if not installed_version:
        print("Warning: xaffinity CLI not installed, skipping registry sync")
        return 0

    registry_version = get_registry_cli_version(registry_path)

    # Check if sync needed
    if installed_version == registry_version:
        return 0  # Already in sync

    print(f"Registry CLI version ({registry_version}) != installed ({installed_version})")
    print("Regenerating registry...")

    if not regenerate_registry():
        print("Failed to regenerate registry", file=sys.stderr)
        return 1

    print(f"Updated mcp/server.d/registry/commands.json to CLI v{installed_version}")
    return 1  # Files modified, pre-commit will re-stage


if __name__ == "__main__":
    sys.exit(main())
