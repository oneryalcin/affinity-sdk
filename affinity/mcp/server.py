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

# Static resources (embedded to avoid file path issues with uvx)
_INTERACTION_ENUMS = {
    "interactionTypes": [
        {"value": "call", "label": "Phone Call", "description": "Voice call with a contact"},
        {"value": "meeting", "label": "Meeting", "description": "Scheduled meeting (video or in-person)"},
        {"value": "email", "label": "Email", "description": "Email correspondence"},
        {"value": "chat-message", "label": "Chat Message", "description": "Instant message (Slack, Teams, etc.)"},
    ],
    "interactionDirections": [
        {"value": "incoming", "label": "Incoming", "description": "Received from contact"},
        {"value": "outgoing", "label": "Outgoing", "description": "Sent to contact"},
    ],
}

_DATA_MODEL_SUMMARY = """# Affinity Data Model

## Core Concepts

### Companies and Persons (Global Entities)
Exist globally in your CRM, independent of any list.
- Commands: `company ls`, `person ls`, `company get`, `person get`
- Can be added to multiple lists

### Opportunities (List-Scoped Entities)
ONLY exist within a specific list (pipeline).
- Commands: `opportunity ls`, `opportunity get`
- Each opportunity belongs to exactly ONE list

### Lists (Collections with Custom Fields)
Pipelines/collections that organize entities with custom Fields.
- Commands: `list ls`, `list get`, `list export`

### List Entries (Entity + List Membership)
When an entity is added to a list, it becomes a List Entry with field values.
- Commands: `list export`, `list-entry get`
- Filter by list-specific fields (Status, Stage, etc.)

## Selectors: Names Work Directly
Most commands accept names, IDs, or emails:
```
list export Dealflow --filter "Status=New"
company get "Acme Corp"
person get john@example.com
```

## Common Patterns
- `list export Dealflow --filter 'Status="New"'` - Get entries with filter
- `company get 12345 --expand list-entries` - Check list membership
- `interaction ls --type all --company-id 12345` - Get interactions
- `field ls --list-id Dealflow` - See list fields and dropdown options

## Filter Syntax
`--filter 'field op "value"'` where op is = != =~ (contains) =^ (starts) =$ (ends) > < >= <=
"""


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
    Tool(
        name="get-entity-dossier",
        description="Get comprehensive dossier for a person, company, or opportunity. Aggregates: entity details, relationship strength, recent interactions, notes, and list memberships in one call.",
        inputSchema={
            "type": "object",
            "required": ["entityType", "entityId"],
            "properties": {
                "entityType": {
                    "type": "string",
                    "enum": ["person", "company", "opportunity"],
                    "description": "Entity type"
                },
                "entityId": {
                    "type": "integer",
                    "description": "Entity ID"
                },
                "includeInteractions": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include recent interactions"
                },
                "includeNotes": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include recent notes"
                },
                "includeLists": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include list memberships"
                },
            },
        },
    ),
    Tool(
        name="get-file-url",
        description="Get a presigned URL to download a file. URL valid for 60 seconds. Get file IDs from 'company files ls', 'person files ls', etc.",
        inputSchema={
            "type": "object",
            "required": ["fileId"],
            "properties": {
                "fileId": {
                    "type": "integer",
                    "description": "File ID (from files ls output)"
                },
            },
        },
    ),
    Tool(
        name="read-xaffinity-resource",
        description="Read an xaffinity:// resource.\n\nAvailable:\n- xaffinity://data-model - Affinity data model guide\n- xaffinity://me - Current authenticated user\n- xaffinity://interaction-enums - Interaction type/direction values\n- xaffinity://field-catalogs/{listId} - Field schema for a list",
        inputSchema={
            "type": "object",
            "required": ["uri"],
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Resource URI (e.g., 'xaffinity://data-model', 'xaffinity://me')"
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

            elif name == "get-entity-dossier":
                entity_type = arguments["entityType"]
                entity_id = arguments["entityId"]
                include_interactions = arguments.get("includeInteractions", True)
                include_notes = arguments.get("includeNotes", True)
                include_lists = arguments.get("includeLists", True)

                dossier: dict[str, Any] = {
                    "entity": {"type": entity_type, "id": entity_id},
                    "details": {},
                    "relationshipStrength": None,
                    "recentInteractions": [],
                    "recentNotes": [],
                    "listMemberships": [],
                }

                # Get entity details
                entity_result = _run_cli([entity_type, "get", str(entity_id), "--json"])
                if entity_result.get("ok") and "data" in entity_result:
                    dossier["details"] = entity_result["data"].get(entity_type, {})

                # Get relationship strength (persons only)
                if entity_type == "person":
                    rs_result = _run_cli(["relationship-strength", "ls", "--external-id", str(entity_id), "--json"])
                    if rs_result.get("ok") and "data" in rs_result:
                        strengths = rs_result["data"].get("relationshipStrengths", [])
                        if strengths:
                            dossier["relationshipStrength"] = strengths[0]

                # Get interactions
                if include_interactions:
                    int_result = _run_cli([
                        "interaction", "ls",
                        f"--{entity_type}-id", str(entity_id),
                        "--type", "all", "--days", "365", "--max-results", "10", "--json"
                    ])
                    if int_result.get("ok") and "data" in int_result:
                        dossier["recentInteractions"] = int_result["data"]

                # Get notes
                if include_notes:
                    notes_result = _run_cli([
                        "note", "ls",
                        f"--{entity_type}-id", str(entity_id),
                        "--max-results", "10", "--json"
                    ])
                    if notes_result.get("ok") and "data" in notes_result:
                        dossier["recentNotes"] = notes_result["data"]

                # Get list memberships
                if include_lists:
                    lists_result = _run_cli([
                        "list-entry", "ls",
                        f"--{entity_type}-id", str(entity_id), "--json"
                    ])
                    if lists_result.get("ok") and "data" in lists_result:
                        dossier["listMemberships"] = lists_result["data"].get("entries", [])

                return [TextContent(type="text", text=json.dumps(dossier, indent=2, ensure_ascii=False))]

            elif name == "get-file-url":
                file_id = arguments["fileId"]
                result = _run_cli(["file-url", str(file_id), "--json"])
                if result.get("ok") and "data" in result:
                    return [TextContent(type="text", text=json.dumps(result["data"], indent=2))]
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "read-xaffinity-resource":
                uri = arguments["uri"]
                # Parse URI: xaffinity://resource-name or xaffinity://resource-name/param
                if not uri.startswith("xaffinity://"):
                    return [TextContent(type="text", text=json.dumps({"error": "Invalid URI format"}))]

                path = uri[len("xaffinity://"):]
                parts = path.split("/", 1)
                resource_name = parts[0]
                resource_param = parts[1] if len(parts) > 1 else None

                if resource_name == "data-model":
                    return [TextContent(type="text", text=_DATA_MODEL_SUMMARY)]

                elif resource_name == "interaction-enums":
                    return [TextContent(type="text", text=json.dumps(_INTERACTION_ENUMS, indent=2))]

                elif resource_name == "me":
                    result = _run_cli(["whoami", "--json"])
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif resource_name == "me-person-id":
                    result = _run_cli(["whoami", "--json"])
                    if result.get("ok") and "data" in result:
                        person_id = result["data"].get("user", {}).get("personId")
                        return [TextContent(type="text", text=json.dumps({"personId": person_id}))]
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif resource_name == "field-catalogs" and resource_param:
                    result = _run_cli(["field", "ls", "--list-id", resource_param, "--json"])
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                elif resource_name == "saved-views" and resource_param:
                    result = _run_cli(["list", "get", resource_param, "--json"])
                    if result.get("ok") and "data" in result:
                        views = result["data"].get("list", {}).get("savedViews", [])
                        return [TextContent(type="text", text=json.dumps({"savedViews": views}, indent=2))]
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                else:
                    return [TextContent(type="text", text=json.dumps({"error": f"Unknown resource: {resource_name}"}))]

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
