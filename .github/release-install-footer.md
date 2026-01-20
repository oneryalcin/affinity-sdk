
## Quick Install

**SDK only:**
```bash
pip install affinity-sdk
```

**SDK + CLI:**
```bash
pipx install "affinity-sdk[cli]"
```

**MCP Server for Claude Desktop** (easiest - MCPB bundle):
1. Install CLI: `pipx install "affinity-sdk[cli]"`
2. *(Optional)* Pre-configure API key: `xaffinity config setup-key`
   - If skipped, Claude Desktop will prompt for your API key during install
3. **[Install xaffinity MCP in Claude Desktop]({{MCPB_URL}})** (download and double-click)

**Other MCP clients** (Cursor, Windsurf, VS Code, etc.) require manual configuration - see [MCP docs](https://yaniv-golan.github.io/affinity-sdk/latest/mcp/).

[Full documentation](https://yaniv-golan.github.io/affinity-sdk/latest/) | [MCP Server docs](https://yaniv-golan.github.io/affinity-sdk/latest/mcp/)
