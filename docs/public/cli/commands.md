# Commands

## No-network commands

These commands never call the Affinity API:

- `xaffinity --help`
- `xaffinity completion bash|zsh|fish`
- `xaffinity version` (also `xaffinity --version`)
- `xaffinity config path`
- `xaffinity config init`
- `xaffinity config check-key` (reads files, but never calls API)

## Configuration

### `xaffinity config path`

Show the path to the configuration file.

```bash
xaffinity config path
```

### `xaffinity config init`

Create a new configuration file with template.

```bash
xaffinity config init
xaffinity config init --force  # Overwrite existing
```

### `xaffinity config check-key`

Check if an API key is configured. Returns exit code 0 if key found, 1 if not found.

This command checks (in order):
1. `AFFINITY_API_KEY` environment variable
2. `.env` file in current directory
3. User config file (`config.toml`)

```bash
xaffinity config check-key
xaffinity config check-key --json
xaffinity config check-key && echo "Key exists"
```

The `--json` output includes:
- `configured`: boolean indicating if a key was found
- `source`: where the key was found (`"environment"`, `"dotenv"`, `"config"`, or `null`)

### `xaffinity config setup-key`

Securely configure your Affinity API key. Prompts for the key with hidden input (not echoed to screen).

Options:

- `--scope [project|user]`: Where to store the key
  - `project`: `.env` file in current directory (auto-added to `.gitignore`)
  - `user`: User config file (`config.toml`, with `chmod 600` on Unix)
- `--force`: Overwrite existing key without confirmation
- `--validate/--no-validate`: Test key against API after storing (default: validate)

```bash
# Interactive setup (prompts for scope)
xaffinity config setup-key

# Store in current project's .env file
xaffinity config setup-key --scope project

# Store in user config (works across all projects)
xaffinity config setup-key --scope user

# Overwrite existing key
xaffinity config setup-key --force

# Skip API validation
xaffinity config setup-key --no-validate
```

Get your API key from [Affinity API Settings](https://support.affinity.co/s/article/How-to-Create-and-Manage-API-Keys).

## Global options

These options can be used with any command:

- `--json` / `--output json`: emit machine-readable `CommandResult` JSON to stdout.
- `--trace`: emit request/response/error trace lines to stderr (safe redaction). Recommended with `--no-progress` for long-running commands.
- `--beta`: enable beta endpoints (required for merge commands).

## Identity

### `xaffinity whoami`

Validates credentials and prints tenant/user context.

```bash
xaffinity whoami
xaffinity whoami --json | jq
```

## URL resolution

### `xaffinity resolve-url <url>`

Parses an Affinity UI URL (including tenant hosts like `https://<tenant>.affinity.co/...` or `https://<tenant>.affinity.com/...`) and validates it by fetching the referenced object.

```bash
xaffinity resolve-url "https://app.affinity.co/companies/263169568"
xaffinity resolve-url "https://mydomain.affinity.com/companies/263169568" --json
```

## People

### `xaffinity person search <query>`

`<query>` is a free-text term (typically a name or email address) passed to Affinity's person search.

Options:

- `--with-interaction-dates`: include interaction date data
- `--with-interaction-persons`: include persons for interactions
- `--with-opportunities`: include associated opportunity IDs
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options

```bash
xaffinity person search "alice@example.com"
xaffinity person search "Alice" --all --json
xaffinity person search "Alice" --with-interaction-dates
```

### `xaffinity person ls`

List persons with V2 pagination. Supports field selection and V2 filter expressions.

Options:

- `--field <id-or-name>` (repeatable): field ID or name to include
- `--field-type <type>` (repeatable): field type to include (global, enriched, relationship-intelligence)
- `--filter <expression>`: V2 filter expression (custom fields only)
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options
- `--csv <path>`: write CSV output (requires `--all`)
- `--csv-bom`: write UTF-8 BOM for Excel compatibility

**Note:** `--filter` only works with custom fields. To filter on built-in properties like `type`, `firstName`, etc., use `--json` output with `jq`.

```bash
xaffinity person ls
xaffinity person ls --page-size 50
xaffinity person ls --field-type enriched --all
xaffinity person ls --filter 'Email =~ "@acme.com"'
xaffinity person ls --all --csv people.csv
xaffinity person ls --all --csv people.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

### `xaffinity person get <personSelector>`

Fetch a person by id, UI URL (including tenant hosts), or a resolver selector.

Examples:

```bash
xaffinity person get 26229794
xaffinity person get "https://mydomain.affinity.com/persons/26229794"
xaffinity person get email:alice@example.com
xaffinity person get 'name:"Alice Smith"'
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
xaffinity person get 26229794 --all-fields --expand lists
xaffinity person get 26229794 --expand list-entries --list "Dealflow" --max-results 200
xaffinity person get 26229794 --expand list-entries --list "Dealflow" --list-entry-field Stage --list-entry-field Amount
xaffinity person get 26229794 --expand list-entries --max-results 1 --show-list-entry-fields
xaffinity person get 26229794 --expand list-entries --max-results 1 --show-list-entry-fields --list-entry-fields-scope all
xaffinity person get 26229794 --all-fields --expand lists --json | jq '.data.person.name'
```

### `xaffinity person create`

```bash
xaffinity person create --first-name Ada --last-name Lovelace --email ada@example.com
xaffinity person create --first-name Ada --last-name Lovelace --company-id 224925494
```

### `xaffinity person update <personId>`

```bash
xaffinity person update 26229794 --email ada@example.com --email ada@work.com
xaffinity person update 26229794 --first-name Ada --last-name Byron
```

### `xaffinity person delete <personId>`

```bash
xaffinity person delete 26229794
```

### `xaffinity person merge <primaryId> <duplicateId>`

```bash
xaffinity --beta person merge 111 222
```

### `xaffinity person files dump <personId>`

Downloads all files attached to a person into a folder bundle with a `manifest.json`.

```bash
xaffinity person files dump 12345 --out ./bundle
```

### `xaffinity person files upload <personId>`

Uploads one or more files to a person.

```bash
xaffinity person files upload 12345 --file doc.pdf
xaffinity person files upload 12345 --file a.pdf --file b.pdf
```

## Companies

### `xaffinity company search <query>`

`<query>` is a free-text term (typically a company name or domain) passed to Affinity's company search.

Options:

- `--with-interaction-dates`: include interaction date data
- `--with-interaction-persons`: include persons for interactions
- `--with-opportunities`: include associated opportunity IDs
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options

```bash
xaffinity company search "example.com"
xaffinity company search "Example" --json
xaffinity company search "Example" --with-interaction-dates
```

### `xaffinity company ls`

List companies with V2 pagination. Supports field selection and V2 filter expressions.

Options:

- `--field <id-or-name>` (repeatable): field ID or name to include
- `--field-type <type>` (repeatable): field type to include (global, enriched, relationship-intelligence)
- `--filter <expression>`: V2 filter expression (custom fields only)
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options
- `--csv <path>`: write CSV output (requires `--all`)
- `--csv-bom`: write UTF-8 BOM for Excel compatibility

**Note:** `--filter` only works with custom fields. To filter on built-in properties like `name`, `domain`, etc., use `--json` output with `jq`.

```bash
xaffinity company ls
xaffinity company ls --page-size 50
xaffinity company ls --field-type enriched --all
xaffinity company ls --filter 'Industry = "Software"'
xaffinity company ls --all --csv companies.csv
xaffinity company ls --all --csv companies.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

### `xaffinity company get <companySelector>`

Fetch a company by id, UI URL (including tenant hosts), or a resolver selector.

Examples:

```bash
xaffinity company get 224925494
xaffinity company get "https://mydomain.affinity.com/companies/224925494"
xaffinity company get domain:wellybox.com
xaffinity company get 'name:"WellyBox"'
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
xaffinity company get 224925494 --all-fields --expand lists
xaffinity company get 224925494 --expand list-entries --list "Dealflow" --max-results 200
xaffinity company get 224925494 --expand list-entries --list "Dealflow" --list-entry-field Stage --list-entry-field Amount
xaffinity company get 224925494 --expand list-entries --max-results 1 --show-list-entry-fields
xaffinity company get 224925494 --expand list-entries --max-results 1 --show-list-entry-fields --list-entry-fields-scope all
xaffinity company get 224925494 --expand people --max-results 50
xaffinity company get 224925494 --all-fields --expand lists --json | jq '.data.company.name'
```

### `xaffinity company create`

```bash
xaffinity company create --name "Acme Corp" --domain acme.com
xaffinity company create --name "Acme Corp" --person-id 26229794
```

### `xaffinity company update <companyId>`

```bash
xaffinity company update 224925494 --domain acme.com
xaffinity company update 224925494 --person-id 26229794 --person-id 26229795
```

### `xaffinity company delete <companyId>`

```bash
xaffinity company delete 224925494
```

### `xaffinity company merge <primaryId> <duplicateId>`

```bash
xaffinity --beta company merge 111 222
```

### `xaffinity company files dump <companyId>`

```bash
xaffinity company files dump 9876 --out ./bundle
```

Notes:
- Saved files use the original filename when possible; if multiple files share the same name, the CLI disambiguates by appending the file id.

### `xaffinity company files upload <companyId>`

Uploads one or more files to a company.

```bash
xaffinity company files upload 9876 --file doc.pdf
xaffinity company files upload 9876 --file a.pdf --file b.pdf
```

## Opportunities

### `xaffinity opportunity ls`

List opportunities (basic v2 representation).

Options:

- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options
- `--csv <path>`: write CSV output (requires `--all`)
- `--csv-bom`: write UTF-8 BOM for Excel compatibility

```bash
xaffinity opportunity ls
xaffinity opportunity ls --page-size 200 --all --json
xaffinity opportunity ls --all --csv opportunities.csv
xaffinity opportunity ls --all --csv opportunities.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

### `xaffinity opportunity get <opportunitySelector>`

Fetch an opportunity by id or UI URL (including tenant hosts).

```bash
xaffinity opportunity get 123
xaffinity opportunity get "https://mydomain.affinity.com/opportunities/123"
xaffinity opportunity get 123 --details
```

Notes:
- `--details` fetches a fuller payload with associations and list entries.

### `xaffinity opportunity create`

Create a new opportunity (V1 write path).

```bash
xaffinity opportunity create --name "Series A" --list "Dealflow"
xaffinity opportunity create --name "Series A" --list 123 --person-id 1 --company-id 2
```

### `xaffinity opportunity update <opportunityId>`

Update an opportunity (replaces association arrays when provided).

```bash
xaffinity opportunity update 123 --name "Series A (Closed)"
xaffinity opportunity update 123 --person-id 1 --person-id 2
```

### `xaffinity opportunity delete <opportunityId>`

```bash
xaffinity opportunity delete 123
```

### `xaffinity opportunity files upload <opportunityId>`

Uploads one or more files to an opportunity.

```bash
xaffinity opportunity files upload 123 --file doc.pdf
xaffinity opportunity files upload 123 --file a.pdf --file b.pdf
```

## Lists

### `xaffinity list ls`

```bash
xaffinity list ls
xaffinity list ls --all --json
```

### `xaffinity list create`

```bash
xaffinity list create --name "Dealflow" --type opportunity --private
xaffinity list create --name "People" --type person --public --owner-id 42
```

### `xaffinity list view <list>`

Accepts a list ID or an exact list name.

The Fields table includes a `valueType` column using V2 string types (e.g., `dropdown-multi`, `ranked-dropdown`).

```bash
xaffinity list view 123
xaffinity list view "My Pipeline" --json
```

### `xaffinity list export <list>`

Exports list entries with selected fields. This is the most powerful CSV export command, supporting custom fields and complex filtering.

Options:

- `--csv <path>`: write CSV output
- `--csv-bom`: write UTF-8 BOM for Excel compatibility
- `--field <id-or-name>` (repeatable): include specific fields
- `--saved-view <name>`: use a saved view's field selection
- `--filter <expression>`: V1 filter expression

```bash
xaffinity list export 123 --csv out.csv
xaffinity list export "My Pipeline" --saved-view "Board" --csv out.csv
xaffinity list export 123 --field Stage --field Amount --filter '"Stage" = "Active"' --csv out.csv
xaffinity list export 123 --csv out.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

### `xaffinity list entry add <list>`

```bash
xaffinity list entry add 123 --person-id 26229794
xaffinity list entry add "Dealflow" --company-id 224925494
```

### `xaffinity list entry delete <list> <entryId>`

```bash
xaffinity list entry delete 123 98765
```

### `xaffinity list entry update-field <list> <entryId>`

```bash
xaffinity list entry update-field 123 98765 --field-id field-123 --value-json '"Active"'
```

### `xaffinity list entry batch-update <list> <entryId>`

```bash
xaffinity list entry batch-update 123 98765 --updates-json '{"field-1": "Active", "field-2": 10}'
```

## Notes

### `xaffinity note ls`

```bash
xaffinity note ls
xaffinity note ls --person-id 123 --json
```

### `xaffinity note get <noteId>`

```bash
xaffinity note get 9876
```

### `xaffinity note create`

```bash
xaffinity note create --content "Met with the team" --person-id 123
xaffinity note create --content "<p>Meeting notes</p>" --type html --company-id 456
```

### `xaffinity note update <noteId>`

```bash
xaffinity note update 9876 --content "Updated note content"
```

### `xaffinity note delete <noteId>`

```bash
xaffinity note delete 9876
```

## Reminders

### `xaffinity reminder ls`

```bash
xaffinity reminder ls
xaffinity reminder ls --owner-id 42 --status active --json
```

### `xaffinity reminder get <reminderId>`

```bash
xaffinity reminder get 12345
```

### `xaffinity reminder create`

```bash
xaffinity reminder create --owner-id 42 --type one-time --due-date 2025-01-15T09:00:00Z --person-id 123
xaffinity reminder create --owner-id 42 --type recurring --reset-type interaction --reminder-days 3 --company-id 456
```

### `xaffinity reminder update <reminderId>`

```bash
xaffinity reminder update 12345 --content "Follow up after demo"
xaffinity reminder update 12345 --completed
```

### `xaffinity reminder delete <reminderId>`

```bash
xaffinity reminder delete 12345
```

## Interactions

### `xaffinity interaction ls`

```bash
xaffinity interaction ls --type email
xaffinity interaction ls --person-id 123 --start-time 2025-01-01T00:00:00Z --end-time 2025-02-01T00:00:00Z
```

### `xaffinity interaction get <interactionId>`

```bash
xaffinity interaction get 2468 --type meeting
```

### `xaffinity interaction create`

```bash
xaffinity interaction create --type meeting --person-id 123 --content "Met to discuss roadmap" --date 2025-01-10T14:00:00Z
xaffinity interaction create --type email --person-id 123 --content "Intro email" --date 2025-01-05T09:15:00Z --direction outgoing
```

### `xaffinity interaction update <interactionId>`

```bash
xaffinity interaction update 2468 --type meeting --content "Updated meeting notes"
```

### `xaffinity interaction delete <interactionId>`

```bash
xaffinity interaction delete 2468 --type meeting
```

## Fields

### `xaffinity field ls`

```bash
xaffinity field ls --entity-type company
xaffinity field ls --list-id 123 --json
```

### `xaffinity field create`

```bash
xaffinity field create --name "Stage" --entity-type opportunity --value-type dropdown --list-specific
```

### `xaffinity field delete <fieldId>`

```bash
xaffinity field delete field-123
```

## Field Values

### `xaffinity field-value ls`

```bash
xaffinity field-value ls --person-id 26229794
xaffinity field-value ls --list-entry-id 98765 --json
```

### `xaffinity field-value create`

```bash
xaffinity field-value create --field-id field-123 --entity-id 26229794 --value \"Investor\"
```

### `xaffinity field-value update <fieldValueId>`

```bash
xaffinity field-value update 555 --value-json '\"Active\"'
```

### `xaffinity field-value delete <fieldValueId>`

```bash
xaffinity field-value delete 555
```

## Field Value Changes

### `xaffinity field-value-changes ls`

List field value change history for a specific field on an entity (V1).

Options:

- `--field-id <id>` (required): Field ID (e.g. `field-123`)
- `--person-id <id>`: Filter by person
- `--company-id <id>`: Filter by company
- `--opportunity-id <id>`: Filter by opportunity
- `--list-entry-id <id>`: Filter by list entry
- `--action-type <type>`: Filter by action (`create`, `update`, `delete`)

Exactly one entity selector (`--person-id`, `--company-id`, `--opportunity-id`, or `--list-entry-id`) is required.

```bash
xaffinity field-value-changes ls --field-id field-123 --person-id 456
xaffinity field-value-changes ls --field-id field-123 --company-id 789 --action-type update
xaffinity --json field-value-changes ls --field-id field-123 --list-entry-id 101
```

## Relationship Strengths

### `xaffinity relationship-strength get`

```bash
xaffinity relationship-strength get --external-id 26229794
xaffinity relationship-strength get --external-id 26229794 --internal-id 42
```

## Tasks

### `xaffinity task get <taskUrl>`

```bash
xaffinity task get https://api.affinity.co/tasks/person-merges/123
```

### `xaffinity task wait <taskUrl>`

```bash
xaffinity task wait https://api.affinity.co/tasks/person-merges/123 --timeout 120
```
