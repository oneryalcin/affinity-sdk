"""
Affinity MCP Server - minimal wrapper around xaffinity CLI.

Run via: uvx --from affinity-sdk[mcp] xaffinity-mcp
"""

from .server import main

__all__ = ["main"]
