# Scripting

## JSON output

Use `--json` for machine-readable output:

```bash
affinity whoami --json | jq
```

## Pagination and resume

Some commands include resume tokens in `meta.pagination`.

- v2 endpoints: `meta.pagination.nextUrl` (resume with `--cursor-url`)
- v1 search: `meta.pagination.nextPageToken` (resume with `--page-token`)

Example (v1 search):

```bash
affinity person search "alice" --json | jq -r '.meta.pagination.nextPageToken'
affinity person search "alice" --page-token "$TOKEN" --json
```

## Artifacts (CSV)

When a command writes a CSV file in `--json` mode, the JSON output includes a reference to the artifact path (and does not duplicate row data).

```bash
affinity list export 123 --csv out.csv --json | jq '.artifacts'
```
