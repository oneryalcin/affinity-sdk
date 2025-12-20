# Scripting

## JSON output

Use `--json` for machine-readable output:

```bash
affinity whoami --json | jq
```

## Pagination and resume

Some commands include resume tokens in `meta.pagination`.

- `meta.pagination` is keyed by section name.
- v2 cursor pagination: `meta.pagination.<section>.nextUrl` (resume with `--cursor <nextUrl>` for commands that support it)
- v1 token pagination: `meta.pagination.<section>.nextPageToken` (resume with `--page-token <token>`)

Example (v1 search):

```bash
affinity person search "alice" --json | jq -r '.meta.pagination.persons.nextPageToken'
affinity person search "alice" --page-token "$TOKEN" --json
```

Example (v2 list inventory):

```bash
affinity list ls --json | jq -r '.meta.pagination.lists.nextUrl'
affinity list ls --cursor "$NEXT_URL" --json
```

Note: if you use `--max-results` and it truncates results mid-page, the CLI may omit pagination to avoid producing an unsafe resume token.

## Artifacts (CSV)

When a command writes a CSV file in `--json` mode, the JSON output includes a reference to the artifact path (and does not duplicate row data).

```bash
affinity list export 123 --csv out.csv --json | jq '.artifacts'
```
