"""JSON help output generator for xaffinity CLI.

Generates machine-readable JSON help output for use by MCP tools and automation.
Invoked via `xaffinity --help --json`.

Commands MUST use @category decorator from affinity.cli.decorators to specify
their classification. Missing @category will raise an error during JSON help
generation to ensure all commands are explicitly categorized.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from click import Argument, Command, Context, Option


class MissingCategoryError(Exception):
    """Raised when a command is missing the required @category decorator."""


def _classify_command(cmd: Command, cmd_name: str) -> tuple[str, bool]:
    """Classify command by category and destructive flag.

    Reads @category and @destructive decorator metadata from the command.
    All commands MUST have an explicit @category decorator.

    Args:
        cmd: Click command object
        cmd_name: Full command name (for error messages)

    Returns:
        Tuple of (category, destructive) where category is "read", "write", or "local"

    Raises:
        MissingCategoryError: If command lacks @category decorator
    """
    category = getattr(cmd, "category", None)
    if category is None:
        raise MissingCategoryError(
            f"Command '{cmd_name}' is missing @category decorator. "
            f"Add @category('read'), @category('write'), or @category('local') "
            f"above @...group.command() decorator."
        )

    destructive = getattr(cmd, "destructive", False)
    return category, destructive


def _get_param_type(param: Option | Argument) -> str:
    """Get the parameter type string for JSON output."""
    from click import BOOL, INT, Choice, Path

    param_type = param.type

    # Handle is_flag for options
    if hasattr(param, "is_flag") and param.is_flag:
        return "flag"

    # Check common types
    if param_type == INT or (hasattr(param_type, "name") and param_type.name == "INT"):
        return "int"
    if param_type == BOOL or (hasattr(param_type, "name") and param_type.name == "BOOL"):
        return "bool"
    if isinstance(param_type, Choice):
        return "string"  # Choices are strings
    if isinstance(param_type, Path):
        return "string"  # Paths are strings

    # Default to string
    return "string"


def _extract_option(opt: Option) -> dict[str, Any]:
    """Extract option metadata for JSON output."""
    result: dict[str, Any] = {
        "type": _get_param_type(opt),
        "required": opt.required,
    }

    # Add multiple flag if applicable
    if opt.multiple:
        result["multiple"] = True

    return result


def _extract_positional(arg: Argument) -> dict[str, Any]:
    """Extract positional argument metadata for JSON output."""
    return {
        "name": arg.name.upper() if arg.name else "ARG",
        "type": _get_param_type(arg),
        "required": arg.required,
    }


def _extract_command(
    cmd: Command,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """Extract command metadata, recursively handling groups.

    Args:
        cmd: Click command or group
        prefix: Command name prefix (e.g., "company" for "company get")

    Returns:
        List of command metadata dictionaries
    """
    from click import Argument, Group, Option

    results: list[dict[str, Any]] = []
    full_name = f"{prefix} {cmd.name}".strip() if prefix else (cmd.name or "")

    # If this is a group, recurse into subcommands
    if isinstance(cmd, Group):
        for subcmd_name in cmd.list_commands(None):  # type: ignore[arg-type]
            subcmd = cmd.get_command(None, subcmd_name)  # type: ignore[arg-type]
            if subcmd:
                results.extend(_extract_command(subcmd, full_name))
        return results

    # Skip the root command itself (no name)
    if not full_name:
        return results

    # Extract description from docstring
    description = cmd.help or ""
    # Take first line only, strip whitespace
    description = description.split("\n")[0].strip()

    # Classify command from decorator metadata (required)
    category, destructive = _classify_command(cmd, full_name)

    # Extract parameters (options) and positionals (arguments)
    parameters: dict[str, dict[str, Any]] = {}
    positionals: list[dict[str, Any]] = []

    # Global options to skip (output format options inherited from parent)
    skip_option_names = {"output", "json_flag", "help"}
    skip_option_flags = {"--json", "-j", "--output", "-o", "--help", "-h"}

    for param in cmd.params:
        if isinstance(param, Option):
            # Skip hidden options
            if param.hidden:
                continue
            # Skip common options that aren't command-specific
            if param.name in skip_option_names:
                continue
            # Skip global output format flags
            if any(opt in skip_option_flags for opt in param.opts):
                continue
            # Get the primary option name (longest form, usually --flag)
            opt_names = param.opts
            primary_name = max(opt_names, key=len) if opt_names else f"--{param.name}"
            parameters[primary_name] = _extract_option(param)
        elif isinstance(param, Argument):
            positionals.append(_extract_positional(param))

    results.append(
        {
            "name": full_name,
            "description": description,
            "category": category,
            "destructive": destructive,
            "parameters": parameters,
            "positionals": positionals,
        }
    )

    return results


def generate_help_json(ctx: Context) -> str:
    """Generate JSON help output for all CLI commands.

    Args:
        ctx: Click context with the root command

    Returns:
        JSON string with command metadata
    """
    # Get the root command (cli group)
    root = ctx.command

    # Extract all commands
    commands: list[dict[str, Any]] = []

    # If root is a group, iterate through subcommands
    from click import Group

    if isinstance(root, Group):
        for cmd_name in root.list_commands(ctx):
            cmd = root.get_command(ctx, cmd_name)
            if cmd:
                commands.extend(_extract_command(cmd))

    # Sort commands by name for consistent output
    commands.sort(key=lambda c: c["name"])

    # Build the output structure
    output = {
        "commands": commands,
    }

    return json.dumps(output, indent=2, ensure_ascii=False)


def emit_help_json_and_exit(ctx: Context) -> None:
    """Generate JSON help and exit.

    Args:
        ctx: Click context
    """
    json_output = generate_help_json(ctx)
    sys.stdout.write(json_output)
    sys.stdout.write("\n")
    sys.exit(0)
