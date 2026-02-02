"""
MCP Server that wraps xaffinity CLI via CLI Gateway pattern.

3 tools expose the entire CLI:
- discover-commands: search available commands
- execute-read-command: run any read command
- execute-write-command: run any write command

Carmack philosophy: CLI already works. Just bridge it to MCP protocol.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Cache for command registry
_command_cache: dict[str, Any] | None = None


def _find_cli() -> str:
    """Find xaffinity CLI."""
    cli = shutil.which("xaffinity")
    if cli:
        return cli
    raise RuntimeError(
        "xaffinity CLI not found. Install with: pip install affinity-sdk[cli]"
    )


def _run_cli(args: list[str], timeout: int = 120, input_data: str | None = None) -> dict[str, Any]:
    """Run xaffinity CLI command and return parsed JSON."""
    cli = _find_cli()
    cmd = [cli] + args

    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"type": "timeout", "message": f"Command timed out after {timeout}s"}}

    # Try to parse as JSON
    try:
        if result.stdout:
            return json.loads(result.stdout)
        return {"ok": False, "error": {"type": "empty", "message": result.stderr or "No output"}}
    except json.JSONDecodeError:
        # Return raw output for non-JSON responses
        return {"ok": result.returncode == 0, "output": result.stdout, "stderr": result.stderr}


def _get_all_commands() -> list[dict[str, Any]]:
    """Get all CLI commands from help JSON."""
    global _command_cache
    if _command_cache is not None:
        return _command_cache.get("commands", [])

    # Get help from each command group
    groups = ["company", "person", "list", "opportunity", "note", "reminder",
              "webhook", "interaction", "field", "task", "config"]

    all_commands: list[dict[str, Any]] = []
    cli = _find_cli()

    for group in groups:
        try:
            result = subprocess.run(
                [cli, group, "--help", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                if "commands" in data:
                    all_commands.extend(data["commands"])
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            continue

    _command_cache = {"commands": all_commands}
    return all_commands


def _search_commands(query: str, category: str = "all", limit: int = 10) -> list[dict[str, Any]]:
    """Search commands by keyword."""
    commands = _get_all_commands()
    query_lower = query.lower()

    results = []
    for cmd in commands:
        # Filter by category
        if category != "all" and cmd.get("category") != category:
            continue

        # Search in name and description
        name = cmd.get("name", "").lower()
        desc = cmd.get("description", "").lower()

        if query_lower in name or query_lower in desc:
            results.append(cmd)

    return results[:limit]


def _format_commands_text(commands: list[dict[str, Any]], detail: str = "summary") -> str:
    """Format commands as compact text."""
    if not commands:
        return "No matching commands found."

    lines = []
    if detail == "list":
        lines.append("# Commands")
        for cmd in commands:
            lines.append(f"- {cmd['name']}")
    elif detail == "summary":
        lines.append("# cmd | category | description")
        for cmd in commands:
            cat = cmd.get("category", "?")[0]  # First letter: r/w/l
            desc = cmd.get("description", "")[:60]
            lines.append(f"{cmd['name']} | {cat} | {desc}")
    else:  # full
        for cmd in commands:
            lines.append(f"## {cmd['name']}")
            lines.append(f"Category: {cmd.get('category', 'unknown')}")
            lines.append(f"Description: {cmd.get('description', '')}")
            if cmd.get("destructive"):
                lines.append("⚠️ DESTRUCTIVE")
            params = cmd.get("parameters", {})
            if params:
                lines.append("Parameters:")
                for p, info in params.items():
                    req = " (required)" if info.get("required") else ""
                    lines.append(f"  {p}: {info.get('type', '?')}{req} - {info.get('help', '')}")
            pos = cmd.get("positionals", [])
            if pos:
                lines.append("Positional args:")
                for p in pos:
                    req = " (required)" if p.get("required") else ""
                    lines.append(f"  {p['name']}: {p.get('type', '?')}{req}")
            lines.append("")

    return "\n".join(lines)


# Tool definitions - CLI Gateway pattern
TOOLS: list[Tool] = [
    Tool(
        name="discover-commands",
        description="Search CLI commands by keyword. Use this first to find the right command.\n\nExamples: 'find companies', 'create person', 'export list', 'log meeting'",
        inputSchema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What you want to do (e.g., 'find companies', 'create person', 'export list entries')"
                },
                "category": {
                    "type": "string",
                    "enum": ["read", "write", "all"],
                    "default": "all",
                    "description": "Filter: 'read' (get/list), 'write' (create/update/delete), 'all'"
                },
                "detail": {
                    "type": "string",
                    "enum": ["list", "summary", "full"],
                    "default": "summary",
                    "description": "Detail level: 'list' (names), 'summary' (+description), 'full' (+parameters)"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Max results"
                },
            },
        },
    ),
    Tool(
        name="execute-read-command",
        description="Execute a read-only CLI command. Use discover-commands first to find the command.\n\nNote: --json is added automatically.\n\nExamples:\n- command='person get', argv=['email:john@example.com']\n- command='company ls', argv=['--filter', 'name contains \"Acme\"', '--limit', '50']\n- command='list entries', argv=['Pipeline', '--max-results', '100']",
        inputSchema={
            "type": "object",
            "required": ["command"],
            "properties": {
                "command": {
                    "type": "string",
                    "description": "CLI command (e.g., 'person get', 'company ls', 'list entries')"
                },
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments: IDs first, then flags. Example: ['12345', '--expand', 'list-entries']"
                },
                "timeout": {
                    "type": "integer",
                    "default": 120,
                    "description": "Timeout in seconds"
                },
            },
        },
    ),
    Tool(
        name="execute-write-command",
        description="Execute a write CLI command (create/update/delete). Use discover-commands first.\n\nFor destructive commands (delete), set confirm=true.\n\nExamples:\n- command='person create', argv=['--first-name', 'John', '--last-name', 'Doe']\n- command='note create', argv=['--content', 'Meeting notes', '--person-id', '123']\n- command='company delete', argv=['456'], confirm=true",
        inputSchema={
            "type": "object",
            "required": ["command"],
            "properties": {
                "command": {
                    "type": "string",
                    "description": "CLI command (e.g., 'person create', 'note create', 'company delete')"
                },
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments"
                },
                "confirm": {
                    "type": "boolean",
                    "default": False,
                    "description": "Required for destructive commands (delete). Adds --yes flag."
                },
                "timeout": {
                    "type": "integer",
                    "default": 60,
                    "description": "Timeout in seconds"
                },
            },
        },
    ),
    Tool(
        name="query",
        description="Execute structured query against Affinity. Supports filtering, includes, aggregates.\n\nEntities: persons, companies, opportunities, listEntries, interactions, notes\n\nExamples:\n- {\"from\": \"persons\", \"where\": {\"path\": \"email\", \"op\": \"contains\", \"value\": \"@acme.com\"}, \"limit\": 50}\n- {\"from\": \"listEntries\", \"where\": {\"path\": \"listName\", \"op\": \"eq\", \"value\": \"Pipeline\"}, \"limit\": 100}",
        inputSchema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "object",
                    "required": ["from"],
                    "properties": {
                        "from": {"type": "string", "enum": ["persons", "companies", "opportunities", "listEntries", "interactions", "notes"]},
                        "where": {"type": "object", "description": "Filter: {path, op, value} or {and/or: [...]}"},
                        "select": {"type": "array", "items": {"type": "string"}},
                        "include": {"type": "array", "items": {"type": "string"}},
                        "orderBy": {"type": "array"},
                        "groupBy": {"type": "string"},
                        "aggregate": {"type": "object"},
                        "limit": {"type": "integer"},
                    },
                },
                "dry_run": {"type": "boolean", "default": False, "description": "Preview execution plan"},
                "format": {
                    "type": "string",
                    "enum": ["json", "toon", "markdown", "csv"],
                    "default": "json",
                    "description": "Output format. 'toon' saves ~40% tokens for large results."
                },
            },
        },
    ),
]


async def serve() -> None:
    """Run the MCP server."""
    server = Server("affinity")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            if name == "discover-commands":
                query = arguments["query"]
                category = arguments.get("category", "all")
                detail = arguments.get("detail", "summary")
                limit = arguments.get("limit", 10)

                commands = _search_commands(query, category, limit)
                output = _format_commands_text(commands, detail)
                return [TextContent(type="text", text=output)]

            elif name == "execute-read-command":
                command = arguments["command"]
                argv = arguments.get("argv", [])
                timeout = arguments.get("timeout", 120)

                # Build CLI args: split command + argv + --json
                cmd_parts = command.split()
                full_args = cmd_parts + argv + ["--json"]

                result = _run_cli(full_args, timeout=timeout)
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "execute-write-command":
                command = arguments["command"]
                argv = arguments.get("argv", [])
                confirm = arguments.get("confirm", False)
                timeout = arguments.get("timeout", 60)

                # Build CLI args
                cmd_parts = command.split()
                full_args = cmd_parts + argv

                # Add --yes for destructive commands if confirmed
                if confirm:
                    full_args.append("--yes")

                full_args.append("--json")

                result = _run_cli(full_args, timeout=timeout)
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            elif name == "query":
                query_obj = arguments["query"]
                dry_run = arguments.get("dry_run", False)
                fmt = arguments.get("format", "json")

                # Build query command
                query_json = json.dumps(query_obj)
                args = ["query", "--stdin", "--output", fmt]
                if dry_run:
                    args.append("--dry-run")

                result = _run_cli(args, timeout=300, input_data=query_json)
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"ok": False, "error": str(e)}))]

    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point for xaffinity-mcp command."""
    try:
        _find_cli()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(serve())


if __name__ == "__main__":
    main()
