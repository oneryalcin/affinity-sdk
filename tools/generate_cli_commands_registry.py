#!/usr/bin/env python3
"""
Generate CLI commands registry for MCP discover-commands tool.

Uses `xaffinity --help --json` to get machine-readable help output from the CLI.
Writes to mcp/.registry/commands.json (bundled via MCPB_INCLUDE).

Usage:
    python tools/generate_cli_commands_registry.py

Requirements:
    - xaffinity CLI must be installed and in PATH
    - CLI must support `--help --json` for machine-readable help output

CI Integration:
    Add to .github/workflows/ci.yml:
        - name: Verify CLI commands registry is up to date
          run: |
            python tools/generate_cli_commands_registry.py
            git diff --exit-code mcp/.registry/commands.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


def get_pyproject_version() -> str:
    """Get version from pyproject.toml (source of truth)."""
    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_cli_version() -> str:
    """Get xaffinity CLI version string."""
    result = subprocess.run(
        ["xaffinity", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Output format: "xaffinity, version 0.7.0"
    return result.stdout.strip().split()[-1]


def validate_cli_version(cli_version: str) -> None:
    """Warn if installed CLI version doesn't match pyproject.toml."""
    try:
        pyproject_version = get_pyproject_version()
        if cli_version != pyproject_version:
            print(
                f"WARNING: Installed CLI version ({cli_version}) doesn't match "
                f"pyproject.toml ({pyproject_version}).",
                file=sys.stderr,
            )
            print(
                "Run 'pip install -e .[cli]' to update the CLI before committing.",
                file=sys.stderr,
            )
    except (FileNotFoundError, KeyError):
        pass  # Skip validation if pyproject.toml not found


def get_commands_json() -> dict:
    """Get machine-readable command list from CLI.

    Uses `xaffinity --help --json` to get JSON output.
    """
    result = subprocess.run(
        ["xaffinity", "--help", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def load_manual_metadata(metadata_path: Path) -> dict[str, dict]:
    """Load manual metadata for commands (relatedCommands, whenToUse, etc).

    Returns a dict mapping command name to metadata dict.
    """
    if not metadata_path.exists():
        return {}
    try:
        data = json.loads(metadata_path.read_text())
        # Remove the _comment key if present
        data.pop("_comment", None)
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def merge_metadata(commands: list[dict], metadata: dict[str, dict]) -> list[dict]:
    """Merge manual metadata into auto-generated commands."""
    for cmd in commands:
        cmd_name = cmd.get("name", "")
        if cmd_name in metadata:
            cmd_meta = metadata[cmd_name]
            if "relatedCommands" in cmd_meta:
                cmd["relatedCommands"] = cmd_meta["relatedCommands"]
            if "whenToUse" in cmd_meta:
                cmd["whenToUse"] = cmd_meta["whenToUse"]
            # Merge examples (manual examples replace auto-generated ones)
            if "examples" in cmd_meta:
                cmd["examples"] = cmd_meta["examples"]
    return commands


def sort_registry(commands: list[dict]) -> list[dict]:
    """Sort commands and their parameters for deterministic output."""
    sorted_commands = sorted(commands, key=lambda c: c["name"])
    for cmd in sorted_commands:
        if cmd.get("parameters"):
            cmd["parameters"] = dict(sorted(cmd["parameters"].items()))
        if cmd.get("positionals"):
            # Keep positionals in order (they're positional!)
            pass
    return sorted_commands


def generate_registry(output_path: Path) -> None:
    """Generate the CLI commands registry file."""
    try:
        cli_version = get_cli_version()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error: Cannot get CLI version: {e}", file=sys.stderr)
        print("Make sure xaffinity CLI is installed and in PATH", file=sys.stderr)
        sys.exit(1)

    # Warn if installed CLI doesn't match pyproject.toml
    validate_cli_version(cli_version)

    try:
        commands_data = get_commands_json()
    except subprocess.CalledProcessError as e:
        print(f"Error: CLI returned error: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: CLI did not return valid JSON: {e}", file=sys.stderr)
        print("Make sure CLI supports --help --json", file=sys.stderr)
        sys.exit(1)

    commands = commands_data.get("commands", [])
    if not commands:
        print("Warning: No commands found in CLI help output", file=sys.stderr)

    # Load and merge manual metadata (relatedCommands, whenToUse, etc.)
    metadata_path = output_path.parent / "commands-metadata.json"
    manual_metadata = load_manual_metadata(metadata_path)
    if manual_metadata:
        commands = merge_metadata(commands, manual_metadata)
        enriched_count = sum(1 for c in commands if c.get("relatedCommands") or c.get("whenToUse"))
        print(f"Merged manual metadata for {enriched_count} commands")

    sorted_commands = sort_registry(commands)

    # Build registry with generation metadata (no timestamp - causes CI drift)
    registry = {
        "_generated": {
            "by": "tools/generate_cli_commands_registry.py",
            "cliVersion": cli_version,
        },
        "version": 1,
        "cliVersion": cli_version,
        "commands": sorted_commands,
        "total": len(sorted_commands),
    }

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with consistent formatting
    output_path.write_text(
        json.dumps(registry, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    )

    print(f"Generated {output_path} with {len(sorted_commands)} commands (CLI v{cli_version})")


def main() -> None:
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    output_path = repo_root / "mcp" / ".registry" / "commands.json"
    generate_registry(output_path)


if __name__ == "__main__":
    main()
