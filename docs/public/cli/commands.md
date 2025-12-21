# Commands

## No-network commands

These commands never call the Affinity API:

- `affinity --help`
- `affinity completion bash|zsh|fish`
- `affinity version` (also `affinity --version`)
- `affinity config path`
- `affinity config init`

## Global options

These options can be used with any command:

- `--json` / `--output json`: emit machine-readable `CommandResult` JSON to stdout.
- `--trace`: emit request/response/error trace lines to stderr (safe redaction). Recommended with `--no-progress` for long-running commands.

## Identity

### `affinity whoami`

Validates credentials and prints tenant/user context.

```bash
affinity whoami
affinity whoami --json | jq
```

## URL resolution

### `affinity resolve-url <url>`

Parses an Affinity UI URL (including tenant hosts like `https://<tenant>.affinity.co/...` or `https://<tenant>.affinity.com/...`) and validates it by fetching the referenced object.

```bash
affinity resolve-url "https://app.affinity.co/companies/263169568"
affinity resolve-url "https://mydomain.affinity.com/companies/263169568" --json
```

## People

### `affinity person search <query>`

`<query>` is a free-text term (typically a name or email address) passed to Affinity's person search.

```bash
affinity person search "alice@example.com"
affinity person search "Alice" --all --json
```

### `affinity person get <personSelector>`

Fetch a person by id, UI URL (including tenant hosts), or a resolver selector.

Examples:

```bash
affinity person get 26229794
affinity person get "https://mydomain.affinity.com/persons/26229794"
affinity person get email:alice@example.com
affinity person get 'name:"Alice Smith"'
```

Field selection:

- `--all-fields`: include all supported (non-list-specific) fields.
- `--field <id-or-exact-name>` (repeatable)
- `--field-type <type>` (repeatable)
- `--no-fields`: skip fields entirely.

Expansions:

- `--expand lists`: include lists the person is on (auto-paginates up to a safe cap; use `--max-results` / `--all` to adjust).
- `--expand list-entries`: include list entries for the person (first page by default; use `--max-results` / `--all` to fetch more).
- `--list <id-or-exact-name>`: filter list entries to a specific list (requires `--expand list-entries`).
- `--list-entry-field <id-or-exact-name>` (repeatable): project list-entry fields into columns (requires `--expand list-entries`). Field names are only allowed with `--list`.
- `--show-list-entry-fields`: render per-list-entry Fields tables in human output (requires `--expand list-entries` and `--max-results <= 3`). Mutually exclusive with `--list-entry-field`.
- `--list-entry-fields-scope list-only|all`: control which fields appear in list-entry tables (human output only).

```bash
affinity person get 26229794 --all-fields --expand lists
affinity person get 26229794 --expand list-entries --list "Dealflow" --max-results 200
affinity person get 26229794 --expand list-entries --list "Dealflow" --list-entry-field Stage --list-entry-field Amount
affinity person get 26229794 --expand list-entries --max-results 1 --show-list-entry-fields
affinity person get 26229794 --expand list-entries --max-results 1 --show-list-entry-fields --list-entry-fields-scope all
affinity person get 26229794 --all-fields --expand lists --json | jq '.data.person.name'
```

### `affinity person files dump <personId>`

Downloads all files attached to a person into a folder bundle with a `manifest.json`.

```bash
affinity person files dump 12345 --out ./bundle
```

## Companies

### `affinity company search <query>`

`<query>` is a free-text term (typically a company name or domain) passed to Affinity's company search.

```bash
affinity company search "example.com"
affinity company search "Example" --json
```

### `affinity company get <companySelector>`

Fetch a company by id, UI URL (including tenant hosts), or a resolver selector.

Examples:

```bash
affinity company get 224925494
affinity company get "https://mydomain.affinity.com/companies/224925494"
affinity company get domain:wellybox.com
affinity company get 'name:"WellyBox"'
```

Field selection:

- `--all-fields`: include all supported (non-list-specific) fields.
- `--field <id-or-exact-name>` (repeatable)
- `--field-type <type>` (repeatable)
- `--no-fields`: skip fields entirely.

Expansions:

- `--expand lists`: include lists the company is on (auto-paginates up to a safe cap; use `--max-results` / `--all` to adjust).
- `--expand list-entries`: include list entries for the company (first page by default; use `--max-results` / `--all` to fetch more).
- `--expand people`: include people associated with the company (use `--max-results` / `--all` to control volume).
- `--list <id-or-exact-name>`: filter list entries to a specific list (requires `--expand list-entries`).
- `--list-entry-field <id-or-exact-name>` (repeatable): project list-entry fields into columns (requires `--expand list-entries`). Field names are only allowed with `--list`.
- `--show-list-entry-fields`: render per-list-entry Fields tables in human output (requires `--expand list-entries` and `--max-results <= 3`). Mutually exclusive with `--list-entry-field`.
- `--list-entry-fields-scope list-only|all`: control which fields appear in list-entry tables (human output only).

```bash
affinity company get 224925494 --all-fields --expand lists
affinity company get 224925494 --expand list-entries --list "Dealflow" --max-results 200
affinity company get 224925494 --expand list-entries --list "Dealflow" --list-entry-field Stage --list-entry-field Amount
affinity company get 224925494 --expand list-entries --max-results 1 --show-list-entry-fields
affinity company get 224925494 --expand list-entries --max-results 1 --show-list-entry-fields --list-entry-fields-scope all
affinity company get 224925494 --expand people --max-results 50
affinity company get 224925494 --all-fields --expand lists --json | jq '.data.company.name'
```

### `affinity company files dump <companyId>`

```bash
affinity company files dump 9876 --out ./bundle
```

Notes:
- Saved files use the original filename when possible; if multiple files share the same name, the CLI disambiguates by appending the file id.

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
