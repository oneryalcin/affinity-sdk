# Commands

## No-network commands

These commands never call the Affinity API:

- `affinity --help`
- `affinity completion bash|zsh|fish`
- `affinity version` (also `affinity --version`)
- `affinity config path`
- `affinity config init`

## Identity

### `affinity whoami`

Validates credentials and prints tenant/user context.

```bash
affinity whoami
affinity whoami --json | jq
```

## URL resolution

### `affinity resolve-url <url>`

Parses an Affinity UI URL (including tenant hosts like `https://<tenant>.affinity.co/...`) and validates it by fetching the referenced object.

```bash
affinity resolve-url "https://app.affinity.co/companies/263169568"
affinity resolve-url "https://lool.affinity.co/companies/263169568" --json
```

## People

### `affinity person search <query>`

```bash
affinity person search "alice@example.com"
affinity person search "Alice" --all --json
```

### `affinity person files dump <personId>`

Downloads all files attached to a person into a folder bundle with a `manifest.json`.

```bash
affinity person files dump 12345 --out ./bundle
```

## Companies

### `affinity company search <query>`

```bash
affinity company search "example.com"
affinity company search "Example" --json
```

### `affinity company files dump <companyId>`

```bash
affinity company files dump 9876 --out ./bundle
```

## Lists

### `affinity list ls`

```bash
affinity list ls
affinity list ls --all --json
```

### `affinity list view <list>`

Accepts a list ID or an exact list name.

The Fields table includes a `valueType` column using V2 string types (e.g., `dropdown-multi`, `ranked-dropdown`).

```bash
affinity list view 123
affinity list view "My Pipeline" --json
```

### `affinity list export <list>`

Exports list entries with selected fields.

```bash
affinity list export 123 --csv out.csv
affinity list export "My Pipeline" --saved-view "Board" --csv out.csv
affinity list export 123 --field Stage --field Amount --filter '"Stage" = "Active"' --csv out.csv
```
