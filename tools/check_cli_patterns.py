#!/usr/bin/env python3
"""
Pre-commit hook to enforce CLI serialization patterns.

This script checks for direct model_dump() calls in CLI command files and
suggests using serialize_model_for_cli() instead.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def check_file(filepath: Path) -> list[str]:
    """
    Check a file for improper model_dump() usage.

    Returns:
        List of error messages (empty if file passes)
    """
    # Only check files in affinity/cli/commands/
    if not str(filepath).startswith("affinity/cli/commands/"):
        return []

    # Skip files that are allowed to have TODOs during migration
    allowed_todo_files = {
        "affinity/cli/commands/field_cmds.py",
        "affinity/cli/commands/field_value_cmds.py",
    }

    content = filepath.read_text()
    errors = []

    # Pattern 1: Direct model_dump() calls without serialize_model_for_cli import
    # Look for .model_dump( with by_alias=True
    model_dump_pattern = r"\.model_dump\([^)]*by_alias=True[^)]*\)"

    # Check if file has serialize_model_for_cli import
    has_import = (
        "from affinity.cli.serialization import serialize_model_for_cli" in content
        or "from ..serialization import serialize_model_for_cli" in content
    )

    # Check if file has TODO comment allowing direct model_dump
    has_todo = "TODO: Migrate to use serialize_model_for_cli()" in content

    # Find all model_dump calls
    for match in re.finditer(model_dump_pattern, content):
        line_num = content[: match.start()].count("\n") + 1

        # Allow direct model_dump if:
        # 1. File has TODO comment (migration in progress), OR
        # 2. File is in allowed list
        if has_todo and str(filepath) in allowed_todo_files:
            # Allowed during migration
            continue

        # If no import and not in migration, suggest using helper
        if not has_import:
            errors.append(
                f"{filepath}:{line_num}: Found direct model_dump() call. "
                f"Import and use serialize_model_for_cli() instead.\n"
                f"  See: docs/cli-development-guide.md#model-serialization"
            )

    # Pattern 2: model_dump() without mode="json"
    # This is critical - catches cases where mode="json" is missing
    model_dump_no_json_pattern = r'\.model_dump\([^)]*by_alias=True(?![^)]*mode="json")[^)]*\)'

    for match in re.finditer(model_dump_no_json_pattern, content):
        # Skip if this file has TODO (migration in progress)
        if has_todo and str(filepath) in allowed_todo_files:
            continue

        line_num = content[: match.start()].count("\n") + 1
        errors.append(
            f'{filepath}:{line_num}: model_dump() missing mode="json" parameter. '
            f"This will cause datetime serialization errors.\n"
            f"  Use: serialize_model_for_cli(model) instead"
        )

    return errors


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check CLI command files for proper serialization patterns"
    )
    parser.add_argument("filenames", nargs="*", help="Filenames to check")
    args = parser.parse_args()

    all_errors = []
    for filename in args.filenames:
        filepath = Path(filename)
        if filepath.exists() and filepath.suffix == ".py":
            errors = check_file(filepath)
            all_errors.extend(errors)

    if all_errors:
        print("❌ CLI serialization pattern violations found:\n")
        for error in all_errors:
            print(error)
        print(
            "\n💡 Tip: Use serialize_model_for_cli() from affinity.cli.serialization "
            "instead of calling model_dump() directly."
        )
        print("📖 See: docs/cli-development-guide.md#model-serialization\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
