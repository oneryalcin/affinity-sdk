# Scripting

## JSON output

Use `--json` for machine-readable output:

```bash
affinity whoami --json | jq
```

## Pagination and resume

Some commands include resume tokens in `meta.pagination`.

- `meta.pagination` is keyed by section name.
- Resume cursor: `meta.pagination.<section>.nextCursor` (resume with `--cursor <cursor>`)
- Treat cursors as opaque strings (some may look like URLs); don’t parse them.

Example (search):

```bash
affinity person search "alice" --json | jq -r '.meta.pagination.persons.nextCursor'
affinity person search "alice" --cursor "$CURSOR" --json
```

Example (list inventory):

```bash
affinity list ls --json | jq -r '.meta.pagination.lists.nextCursor'
affinity list ls --cursor "$CURSOR" --json
```

Note: if you use `--max-results` and it truncates results mid-page, the CLI may omit pagination to avoid producing an unsafe resume token.

## Artifacts (CSV)

When a command writes a CSV file in `--json` mode, the JSON output includes a reference to the artifact path (and does not duplicate row data).

```bash
affinity list export 123 --csv out.csv --json | jq '.artifacts'
```
