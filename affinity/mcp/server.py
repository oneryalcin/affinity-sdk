"""
MCP Server that wraps xaffinity CLI.

Carmack philosophy: CLI already works. Just bridge it to MCP protocol.
Zero business logic duplication.
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


def _find_cli() -> str:
    """Find xaffinity CLI, preferring the one from our package."""
    # Try the entry point from our package first
    cli = shutil.which("xaffinity")
    if cli:
        return cli
    # Fallback: maybe running in dev mode
    raise RuntimeError(
        "xaffinity CLI not found. Install with: pip install affinity-sdk[cli]"
    )


def _run_cli(args: list[str], timeout: int = 120) -> dict[str, Any]:
    """Run xaffinity CLI command and return parsed JSON."""
    cli = _find_cli()
    cmd = [cli] + args + ["--json"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"type": "timeout", "message": f"Command timed out after {timeout}s"}}

    # CLI always outputs JSON with --json flag
    try:
        return json.loads(result.stdout) if result.stdout else {"ok": False, "error": {"type": "empty", "message": result.stderr or "No output"}}
    except json.JSONDecodeError:
        return {"ok": False, "error": {"type": "parse_error", "message": result.stderr or result.stdout}}


# Tool definitions - maps MCP tools to CLI commands
TOOLS: list[Tool] = [
    Tool(
        name="company-get",
        description="Get a company by ID, domain, or name. Selector formats: 12345, domain:acme.com, name:\"Acme Inc\"",
        inputSchema={
            "type": "object",
            "required": ["selector"],
            "properties": {
                "selector": {"type": "string", "description": "Company ID, domain:xxx, or name:\"xxx\""},
                "expand": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["list-entries", "interactions", "opportunities"]},
                    "description": "Related data to include"
                },
            },
        },
    ),
    Tool(
        name="company-list",
        description="List companies with optional filtering",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 100, "description": "Max results"},
                "filter": {"type": "string", "description": "Filter expression (e.g., name contains \"tech\")"},
            },
        },
    ),
    Tool(
        name="person-get",
        description="Get a person by ID or email. Selector formats: 12345, email:john@acme.com",
        inputSchema={
            "type": "object",
            "required": ["selector"],
            "properties": {
                "selector": {"type": "string", "description": "Person ID or email:xxx"},
                "expand": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["list-entries", "interactions", "companies"]},
                    "description": "Related data to include"
                },
            },
        },
    ),
    Tool(
        name="person-search",
        description="Search persons by term (name, email, etc)",
        inputSchema={
            "type": "object",
            "required": ["term"],
            "properties": {
                "term": {"type": "string", "description": "Search term"},
                "limit": {"type": "integer", "default": 25},
            },
        },
    ),
    Tool(
        name="list-get",
        description="Get a list by ID or name",
        inputSchema={
            "type": "object",
            "required": ["selector"],
            "properties": {
                "selector": {"type": "string", "description": "List ID or name:\"List Name\""},
            },
        },
    ),
    Tool(
        name="list-entries",
        description="Get entries from a list",
        inputSchema={
            "type": "object",
            "required": ["list_selector"],
            "properties": {
                "list_selector": {"type": "string", "description": "List ID or name"},
                "limit": {"type": "integer", "default": 100},
            },
        },
    ),
    Tool(
        name="opportunity-get",
        description="Get an opportunity by ID",
        inputSchema={
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer", "description": "Opportunity ID"},
            },
        },
    ),
    Tool(
        name="note-list",
        description="List notes for a person, company, or opportunity",
        inputSchema={
            "type": "object",
            "properties": {
                "person_id": {"type": "integer"},
                "company_id": {"type": "integer"},
                "opportunity_id": {"type": "integer"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    ),
    Tool(
        name="interaction-list",
        description="List interactions for a person or company",
        inputSchema={
            "type": "object",
            "properties": {
                "person_id": {"type": "integer"},
                "company_id": {"type": "integer"},
                "type": {"type": "string", "enum": ["email", "meeting", "call", "chat_message"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
    ),
    Tool(
        name="query",
        description="Execute structured query against Affinity. Supports filtering, includes, aggregates.",
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
                        "orderBy": {"type": "array", "items": {"type": "object"}},
                        "limit": {"type": "integer"},
                    },
                },
                "dry_run": {"type": "boolean", "default": False, "description": "Preview execution plan"},
            },
        },
    ),
]


def _build_cli_args(tool_name: str, arguments: dict[str, Any]) -> list[str]:
    """Convert MCP tool call to CLI args."""
    args: list[str] = []

    if tool_name == "company-get":
        args = ["company", "get", arguments["selector"]]
        for exp in arguments.get("expand") or []:
            args.extend(["--expand", exp])

    elif tool_name == "company-list":
        args = ["company", "list"]
        if limit := arguments.get("limit"):
            args.extend(["--max-results", str(limit)])
        if flt := arguments.get("filter"):
            args.extend(["--filter", flt])

    elif tool_name == "person-get":
        args = ["person", "get", arguments["selector"]]
        for exp in arguments.get("expand") or []:
            args.extend(["--expand", exp])

    elif tool_name == "person-search":
        args = ["person", "search", arguments["term"]]
        if limit := arguments.get("limit"):
            args.extend(["--max-results", str(limit)])

    elif tool_name == "list-get":
        args = ["list", "get", arguments["selector"]]

    elif tool_name == "list-entries":
        args = ["list", "entries", arguments["list_selector"]]
        if limit := arguments.get("limit"):
            args.extend(["--max-results", str(limit)])

    elif tool_name == "opportunity-get":
        args = ["opportunity", "get", str(arguments["id"])]

    elif tool_name == "note-list":
        args = ["note", "list"]
        if pid := arguments.get("person_id"):
            args.extend(["--person-id", str(pid)])
        if cid := arguments.get("company_id"):
            args.extend(["--company-id", str(cid)])
        if oid := arguments.get("opportunity_id"):
            args.extend(["--opportunity-id", str(oid)])
        if limit := arguments.get("limit"):
            args.extend(["--max-results", str(limit)])

    elif tool_name == "interaction-list":
        args = ["interaction", "list"]
        if pid := arguments.get("person_id"):
            args.extend(["--person-id", str(pid)])
        if cid := arguments.get("company_id"):
            args.extend(["--company-id", str(cid)])
        if t := arguments.get("type"):
            args.extend(["--type", t])
        if limit := arguments.get("limit"):
            args.extend(["--max-results", str(limit)])

    elif tool_name == "query":
        # Query uses stdin for the query JSON
        query_json = json.dumps(arguments["query"])
        args = ["query", "--stdin"]
        if arguments.get("dry_run"):
            args.append("--dry-run")
        # Special case: need to pass query via stdin
        return ["__query__", query_json] + args

    return args


async def serve() -> None:
    """Run the MCP server."""
    server = Server("affinity")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        args = _build_cli_args(name, arguments)

        # Special handling for query (needs stdin)
        if args and args[0] == "__query__":
            query_json = args[1]
            cli_args = args[2:]
            cli = _find_cli()
            cmd = [cli] + cli_args + ["--json"]
            try:
                result = subprocess.run(
                    cmd,
                    input=query_json,
                    capture_output=True,
                    text=True,
                    timeout=300,  # queries can be slow
                )
                output = json.loads(result.stdout) if result.stdout else {"ok": False, "error": result.stderr}
            except Exception as e:
                output = {"ok": False, "error": {"type": "exception", "message": str(e)}}
        else:
            output = _run_cli(args)

        # Return as JSON text
        return [TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point for xaffinity-mcp command."""
    # Sanity check: CLI must be available
    try:
        _find_cli()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(serve())


if __name__ == "__main__":
    main()
