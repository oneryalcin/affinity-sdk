# Scripting

## Session caching for pipelines

When running multiple CLI commands in a pipeline, enable session caching to avoid redundant API calls:

```bash
#!/bin/bash
export AFFINITY_SESSION_CACHE=$(xaffinity session start) || exit 1
trap 'xaffinity session end; unset AFFINITY_SESSION_CACHE' EXIT

# Commands share cached metadata (field definitions, list resolution)
xaffinity list export "My List" | xaffinity person get
```

See [Pipeline Optimization](commands.md#pipeline-optimization) for details.

## JSON output

Use `--json` for machine-readable output:

```bash
xaffinity whoami --json | jq
```

## Pagination and resume

Some commands include resume tokens in `meta.pagination`.

- `meta.pagination` is keyed by section name.
- Resume cursor: `meta.pagination.<section>.nextCursor` (resume with `--cursor <cursor>`)
- Treat cursors as opaque strings (some may look like URLs); don’t parse them.

Example (search):

```bash
xaffinity person search "alice" --json | jq -r '.meta.pagination.persons.nextCursor'
xaffinity person search "alice" --cursor "$CURSOR" --json
```

Example (list inventory):

```bash
xaffinity list ls --json | jq -r '.meta.pagination.lists.nextCursor'
xaffinity list ls --cursor "$CURSOR" --json
```

Note: if you use `--max-results` and it truncates results mid-page, the CLI may omit pagination to avoid producing an unsafe resume token.

## Artifacts (CSV)

When a command writes a CSV file in `--json` mode, the JSON output includes a reference to the artifact path (and does not duplicate row data).

```bash
xaffinity list export 123 --csv out.csv --json | jq '.artifacts'
```
