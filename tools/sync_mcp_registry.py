#!/usr/bin/env python3
"""Sync MCP CLI commands registry with CLI introspection.

This pre-commit hook regenerates mcp/.registry/commands.json whenever
CLI command files or pyproject.toml change. This ensures the registry
stays in sync with the actual CLI behavior.

The hook:
1. Validates installed CLI version matches pyproject.toml
2. Regenerates the registry from CLI introspection
3. Returns exit code 1 if files were modified (pre-commit re-stages)
4. Returns exit code 0 if no changes needed

Unlike version-based sync, this approach catches ALL CLI changes
(new options, changed defaults, etc.) not just version bumps.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


def get_pyproject_version() -> str:
    """Get version from pyproject.toml."""
    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_installed_cli_version() -> str | None:
    """Get installed CLI version, or None if not installed."""
    try:
        result = subprocess.run(
            ["xaffinity", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Output format: "xaffinity, version 0.7.0"
        return result.stdout.strip().split()[-1]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def check_version_match() -> bool:
    """Check if installed CLI matches pyproject.toml.

    Returns True if versions match, False otherwise.
    Prints instructions on mismatch.
    """
    pyproject_version = get_pyproject_version()
    cli_version = get_installed_cli_version()

    if cli_version is None:
        print("Error: xaffinity CLI not installed.", file=sys.stderr)
        print("Run: pip install -e '.[cli]'", file=sys.stderr)
        return False

    if cli_version != pyproject_version:
        print(
            f"Error: Installed CLI ({cli_version}) doesn't match "
            f"pyproject.toml ({pyproject_version}).",
            file=sys.stderr,
        )
        print("Run: pip install -e '.[cli]'", file=sys.stderr)
        return False

    return True


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


def registry_changed() -> bool:
    """Check if registry file has uncommitted changes."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "mcp" / ".registry" / "commands.json"

    try:
        result = subprocess.run(
            ["git", "diff", "--quiet", str(registry_path)],
            check=False,
            cwd=repo_root,
            capture_output=True,
        )
        return result.returncode != 0
    except subprocess.CalledProcessError:
        return True  # Assume changed if git fails


def main() -> int:
    """Regenerate registry and signal if modified."""
    # Fail early if CLI version doesn't match pyproject.toml
    if not check_version_match():
        return 1

    if not regenerate_registry():
        print("Failed to regenerate registry", file=sys.stderr)
        return 1

    if registry_changed():
        print("Registry updated - staging changes")
        return 1  # Pre-commit will re-stage

    return 0  # No changes needed


if __name__ == "__main__":
    sys.exit(main())
