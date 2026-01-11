# CLI

The SDK ships an optional `xaffinity` CLI that dogfoods the SDK. Install it as an extra so library-only users don't pay the dependency cost.

## Key Features

- **Query Language**: Complex queries with filtering, aggregations, and includes ([Query Guide](../guides/query-command.md))
- **CSV Export**: Export people, companies, opportunities, and list entries to CSV with `--csv` flag ([CSV Export Guide](../guides/csv-export.md))
- **Filtering**: Server-side filtering on custom fields with `--filter` ([Filtering Guide](../guides/filtering.md))
- **JSON Output**: All commands support `--json` for programmatic use ([Scripting Guide](scripting.md))
- **Datetime Handling**: Local time input, UTC output for JSON ([Datetime Guide](../guides/datetime-handling.md))
- **Pagination**: Fetch all pages with `--all` or control page size with `--page-size`
- **Name Resolution**: Use names instead of IDs for lists, fields, and entities
- **Session Caching**: Share metadata across pipeline commands with `session start/end` ([Pipeline Optimization](commands.md#pipeline-optimization))

See [Commands Reference](commands.md) for complete command documentation.

## AI Integration

### MCP Server

Connect desktop AI tools (Claude Desktop, Cursor, Windsurf, VS Code + Copilot) to Affinity. See [MCP Server](../mcp/index.md).

### Claude Code

Using Claude Code? Install the CLI plugin for AI-assisted usage:

```bash
/plugin marketplace add yaniv-golan/affinity-sdk
/plugin install cli@xaffinity
```

This teaches Claude CLI patterns and provides the `/affinity-help` quick reference command. See [Claude Code plugins](../guides/claude-code-plugins.md) for all available plugins.

## Install

Recommended for end-users:

```bash
pipx install "affinity-sdk[cli]"
```

Or in a virtualenv:

```bash
pip install "affinity-sdk[cli]"
```

## Authentication

The CLI never makes "background" requests. It only calls the API for commands that require it.

### Quick Setup

Check if a key is already configured:

```bash
xaffinity config check-key
```

Set up a new key securely (hidden input, not echoed):

```bash
xaffinity config setup-key
```

See [config check-key](commands.md#xaffinity-config-check-key) and [config setup-key](commands.md#xaffinity-config-setup-key) for details.

### API Key Sources

The CLI checks these sources in order (highest precedence first):

1. `AFFINITY_API_KEY` environment variable
2. `.env` file in current directory (requires `--dotenv` flag)
3. `api_key` in user config file (`~/.config/xaffinity/config.toml`)

### Using .env Files

For project-specific keys, use `--dotenv` to load from `.env`:

```bash
xaffinity --dotenv whoami
xaffinity --dotenv --env-file ./dev.env whoami
```

The `config setup-key --scope project` command creates a `.env` file and adds it to `.gitignore` automatically.

## Output contract

- `--json` is supported on every command.
- In `--json` mode, JSON is written to **stdout**. Progress/logging go to **stderr**.
- Human/table output goes to **stdout**; diagnostics go to **stderr**.
- Commands build a single structured result and then render it as either JSON or table output (no “double implementations”).
- In `--json` mode, `data` is an object keyed by section name (even for single-section commands), and pagination tokens/URLs live in `meta.pagination.<section>`.
- If `--max-results` truncates results mid-page, the CLI may omit `meta.pagination.<section>` to avoid producing an unsafe resume token.

## Performance

The CLI enables SDK in-memory caching for cacheable metadata requests (e.g., field metadata) automatically.

For pipelines running multiple commands, use **session caching** to share metadata across invocations:

```bash
export AFFINITY_SESSION_CACHE=$(xaffinity session start)
xaffinity list export "My List" | xaffinity person get
xaffinity session end
```

See [Pipeline Optimization](commands.md#pipeline-optimization) for details.

## Progress + quiet mode

- Long operations show progress bars/spinners on **stderr** when interactive.
- `-q/--quiet` disables progress and suppresses non-essential stderr output.

## Logging

The CLI writes logs to platform-standard locations (via `platformdirs`), with rotation and redaction.

Override with:

- `--log-file <path>`
- `--no-log-file`

## SDK controls

These flags expose useful SDK behaviors directly from the CLI:

- `--readonly`: disallow write operations (guard rail for scripts).
- `--max-retries N`: tune rate-limit retry behavior.
- `--trace`: trace request/response/error events to stderr (safe redaction).

## Advanced configuration (testing)

For testing against mock servers, these environment variables override API base URLs:

- `AFFINITY_V1_BASE_URL`: Override V1 API base URL (default: `https://api.affinity.co`)
- `AFFINITY_V2_BASE_URL`: Override V2 API base URL (default: `https://api.affinity.co/v2`)

These can also be set per-profile in the config file.

## Exit codes

- `0`: success
- `1`: general error
- `2`: usage/validation error (including ambiguous name resolution)
- `3`: auth/permission error (401/403)
- `4`: not found
- `5`: rate limited or temporary upstream failure (429/5xx after retries)
- `130`: interrupted (Ctrl+C)
- `143`: terminated (SIGTERM)
