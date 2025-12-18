# CLI

The SDK ships an optional `affinity` CLI that dogfoods the SDK. Install it as an extra so library-only users don’t pay the dependency cost.

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

The CLI never makes “background” requests. It only calls the API for commands that require it.

API key sources (highest precedence first):

1. `--api-key-file <path>` (use `-` to read from stdin)
2. `--api-key-stdin` (alias for `--api-key-file -`)
3. `AFFINITY_API_KEY`
4. `api_key` in the config profile (discouraged for shared machines; the CLI warns on unsafe permissions where feasible)

Optional local development: `.env` loading is **opt-in**:

```bash
affinity --dotenv whoami
affinity --dotenv --env-file ./dev.env whoami
```

## Output contract

- `--json` is supported on every command.
- In `--json` mode, JSON is written to **stdout**. Progress/logging go to **stderr**.
- Human/table output goes to **stdout**; diagnostics go to **stderr**.
- Commands build a single structured result and then render it as either JSON or table output (no “double implementations”).

## Progress + quiet mode

- Long operations show progress bars/spinners on **stderr** when interactive.
- `-q/--quiet` disables progress and suppresses non-essential stderr output.

## Logging

The CLI writes logs to platform-standard locations (via `platformdirs`), with rotation and redaction.

Override with:

- `--log-file <path>`
- `--no-log-file`

## Exit codes

- `0`: success
- `1`: general error
- `2`: usage/validation error (including ambiguous name resolution)
- `3`: auth/permission error (401/403)
- `4`: not found
- `5`: rate limited or temporary upstream failure (429/5xx after retries)
- `130`: interrupted (Ctrl+C)
- `143`: terminated (SIGTERM)
