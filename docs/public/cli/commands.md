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
- `--beta`: enable beta endpoints (required for merge commands).

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

Options:

- `--with-interaction-dates`: include interaction date data
- `--with-interaction-persons`: include persons for interactions
- `--with-opportunities`: include associated opportunity IDs
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options

```bash
affinity person search "alice@example.com"
affinity person search "Alice" --all --json
affinity person search "Alice" --with-interaction-dates
```

### `affinity person ls`

List persons with V2 pagination. Supports field selection and V2 filter expressions.

Options:

- `--field <id-or-name>` (repeatable): field ID or name to include
- `--field-type <type>` (repeatable): field type to include (global, enriched, relationship-intelligence)
- `--filter <expression>`: V2 filter expression (custom fields only)
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options
- `--csv <path>`: write CSV output (requires `--all`)
- `--csv-bom`: write UTF-8 BOM for Excel compatibility

**Note:** `--filter` only works with custom fields using `field("Name")` syntax. To filter on built-in properties like `type`, `firstName`, etc., use `--json` output with `jq`.

```bash
affinity person ls
affinity person ls --page-size 50
affinity person ls --field-type enriched --all
affinity person ls --filter 'field("Email") =~ "@acme.com"'
affinity person ls --all --csv people.csv
affinity person ls --all --csv people.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

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

### `affinity person create`

```bash
affinity person create --first-name Ada --last-name Lovelace --email ada@example.com
affinity person create --first-name Ada --last-name Lovelace --company-id 224925494
```

### `affinity person update <personId>`

```bash
affinity person update 26229794 --email ada@example.com --email ada@work.com
affinity person update 26229794 --first-name Ada --last-name Byron
```

### `affinity person delete <personId>`

```bash
affinity person delete 26229794
```

### `affinity person merge <primaryId> <duplicateId>`

```bash
affinity --beta person merge 111 222
```

### `affinity person files dump <personId>`

Downloads all files attached to a person into a folder bundle with a `manifest.json`.

```bash
affinity person files dump 12345 --out ./bundle
```

### `affinity person files upload <personId>`

Uploads one or more files to a person.

```bash
affinity person files upload 12345 --file doc.pdf
affinity person files upload 12345 --file a.pdf --file b.pdf
```

## Companies

### `affinity company search <query>`

`<query>` is a free-text term (typically a company name or domain) passed to Affinity's company search.

Options:

- `--with-interaction-dates`: include interaction date data
- `--with-interaction-persons`: include persons for interactions
- `--with-opportunities`: include associated opportunity IDs
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options

```bash
affinity company search "example.com"
affinity company search "Example" --json
affinity company search "Example" --with-interaction-dates
```

### `affinity company ls`

List companies with V2 pagination. Supports field selection and V2 filter expressions.

Options:

- `--field <id-or-name>` (repeatable): field ID or name to include
- `--field-type <type>` (repeatable): field type to include (global, enriched, relationship-intelligence)
- `--filter <expression>`: V2 filter expression (custom fields only)
- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options
- `--csv <path>`: write CSV output (requires `--all`)
- `--csv-bom`: write UTF-8 BOM for Excel compatibility

**Note:** `--filter` only works with custom fields using `field("Name")` syntax. To filter on built-in properties like `name`, `domain`, etc., use `--json` output with `jq`.

```bash
affinity company ls
affinity company ls --page-size 50
affinity company ls --field-type enriched --all
affinity company ls --filter 'field("Industry") = "Software"'
affinity company ls --all --csv companies.csv
affinity company ls --all --csv companies.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

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

### `affinity company create`

```bash
affinity company create --name "Acme Corp" --domain acme.com
affinity company create --name "Acme Corp" --person-id 26229794
```

### `affinity company update <companyId>`

```bash
affinity company update 224925494 --domain acme.com
affinity company update 224925494 --person-id 26229794 --person-id 26229795
```

### `affinity company delete <companyId>`

```bash
affinity company delete 224925494
```

### `affinity company merge <primaryId> <duplicateId>`

```bash
affinity --beta company merge 111 222
```

### `affinity company files dump <companyId>`

```bash
affinity company files dump 9876 --out ./bundle
```

Notes:
- Saved files use the original filename when possible; if multiple files share the same name, the CLI disambiguates by appending the file id.

### `affinity company files upload <companyId>`

Uploads one or more files to a company.

```bash
affinity company files upload 9876 --file doc.pdf
affinity company files upload 9876 --file a.pdf --file b.pdf
```

## Opportunities

### `affinity opportunity ls`

List opportunities (basic v2 representation).

Options:

- `--page-size`, `--cursor`, `--max-results`, `--all`: pagination options
- `--csv <path>`: write CSV output (requires `--all`)
- `--csv-bom`: write UTF-8 BOM for Excel compatibility

```bash
affinity opportunity ls
affinity opportunity ls --page-size 200 --all --json
affinity opportunity ls --all --csv opportunities.csv
affinity opportunity ls --all --csv opportunities.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

### `affinity opportunity get <opportunitySelector>`

Fetch an opportunity by id or UI URL (including tenant hosts).

```bash
affinity opportunity get 123
affinity opportunity get "https://mydomain.affinity.com/opportunities/123"
affinity opportunity get 123 --details
```

Notes:
- `--details` fetches a fuller payload with associations and list entries.

### `affinity opportunity create`

Create a new opportunity (V1 write path).

```bash
affinity opportunity create --name "Series A" --list "Dealflow"
affinity opportunity create --name "Series A" --list 123 --person-id 1 --company-id 2
```

### `affinity opportunity update <opportunityId>`

Update an opportunity (replaces association arrays when provided).

```bash
affinity opportunity update 123 --name "Series A (Closed)"
affinity opportunity update 123 --person-id 1 --person-id 2
```

### `affinity opportunity delete <opportunityId>`

```bash
affinity opportunity delete 123
```

### `affinity opportunity files upload <opportunityId>`

Uploads one or more files to an opportunity.

```bash
affinity opportunity files upload 123 --file doc.pdf
affinity opportunity files upload 123 --file a.pdf --file b.pdf
```

## Lists

### `affinity list ls`

```bash
affinity list ls
affinity list ls --all --json
```

### `affinity list create`

```bash
affinity list create --name "Dealflow" --type opportunity --private
affinity list create --name "People" --type person --public --owner-id 42
```

### `affinity list view <list>`

Accepts a list ID or an exact list name.

The Fields table includes a `valueType` column using V2 string types (e.g., `dropdown-multi`, `ranked-dropdown`).

```bash
affinity list view 123
affinity list view "My Pipeline" --json
```

### `affinity list export <list>`

Exports list entries with selected fields. This is the most powerful CSV export command, supporting custom fields and complex filtering.

Options:

- `--csv <path>`: write CSV output
- `--csv-bom`: write UTF-8 BOM for Excel compatibility
- `--field <id-or-name>` (repeatable): include specific fields
- `--saved-view <name>`: use a saved view's field selection
- `--filter <expression>`: V1 filter expression

```bash
affinity list export 123 --csv out.csv
affinity list export "My Pipeline" --saved-view "Board" --csv out.csv
affinity list export 123 --field Stage --field Amount --filter '"Stage" = "Active"' --csv out.csv
affinity list export 123 --csv out.csv --csv-bom
```

See the [CSV Export Guide](../guides/csv-export.md) for more details.

### `affinity list entry add <list>`

```bash
affinity list entry add 123 --person-id 26229794
affinity list entry add "Dealflow" --company-id 224925494
```

### `affinity list entry delete <list> <entryId>`

```bash
affinity list entry delete 123 98765
```

### `affinity list entry update-field <list> <entryId>`

```bash
affinity list entry update-field 123 98765 --field-id field-123 --value-json '"Active"'
```

### `affinity list entry batch-update <list> <entryId>`

```bash
affinity list entry batch-update 123 98765 --updates-json '{"field-1": "Active", "field-2": 10}'
```

## Notes

### `affinity note ls`

```bash
affinity note ls
affinity note ls --person-id 123 --json
```

### `affinity note get <noteId>`

```bash
affinity note get 9876
```

### `affinity note create`

```bash
affinity note create --content "Met with the team" --person-id 123
affinity note create --content "<p>Meeting notes</p>" --type html --company-id 456
```

### `affinity note update <noteId>`

```bash
affinity note update 9876 --content "Updated note content"
```

### `affinity note delete <noteId>`

```bash
affinity note delete 9876
```

## Reminders

### `affinity reminder ls`

```bash
affinity reminder ls
affinity reminder ls --owner-id 42 --status active --json
```

### `affinity reminder get <reminderId>`

```bash
affinity reminder get 12345
```

### `affinity reminder create`

```bash
affinity reminder create --owner-id 42 --type one-time --due-date 2025-01-15T09:00:00Z --person-id 123
affinity reminder create --owner-id 42 --type recurring --reset-type interaction --reminder-days 3 --company-id 456
```

### `affinity reminder update <reminderId>`

```bash
affinity reminder update 12345 --content "Follow up after demo"
affinity reminder update 12345 --completed
```

### `affinity reminder delete <reminderId>`

```bash
affinity reminder delete 12345
```

## Interactions

### `affinity interaction ls`

```bash
affinity interaction ls --type email
affinity interaction ls --person-id 123 --start-time 2025-01-01T00:00:00Z --end-time 2025-02-01T00:00:00Z
```

### `affinity interaction get <interactionId>`

```bash
affinity interaction get 2468 --type meeting
```

### `affinity interaction create`

```bash
affinity interaction create --type meeting --person-id 123 --content "Met to discuss roadmap" --date 2025-01-10T14:00:00Z
affinity interaction create --type email --person-id 123 --content "Intro email" --date 2025-01-05T09:15:00Z --direction outgoing
```

### `affinity interaction update <interactionId>`

```bash
affinity interaction update 2468 --type meeting --content "Updated meeting notes"
```

### `affinity interaction delete <interactionId>`

```bash
affinity interaction delete 2468 --type meeting
```

## Fields

### `affinity field ls`

```bash
affinity field ls --entity-type company
affinity field ls --list-id 123 --json
```

### `affinity field create`

```bash
affinity field create --name "Stage" --entity-type opportunity --value-type dropdown --list-specific
```

### `affinity field delete <fieldId>`

```bash
affinity field delete field-123
```

## Field Values

### `affinity field-value ls`

```bash
affinity field-value ls --person-id 26229794
affinity field-value ls --list-entry-id 98765 --json
```

### `affinity field-value create`

```bash
affinity field-value create --field-id field-123 --entity-id 26229794 --value \"Investor\"
```

### `affinity field-value update <fieldValueId>`

```bash
affinity field-value update 555 --value-json '\"Active\"'
```

### `affinity field-value delete <fieldValueId>`

```bash
affinity field-value delete 555
```

## Field Value Changes

### `affinity field-value-changes ls`

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
affinity field-value-changes ls --field-id field-123 --person-id 456
affinity field-value-changes ls --field-id field-123 --company-id 789 --action-type update
affinity --json field-value-changes ls --field-id field-123 --list-entry-id 101
```

## Relationship Strengths

### `affinity relationship-strength get`

```bash
affinity relationship-strength get --external-id 26229794
affinity relationship-strength get --external-id 26229794 --internal-id 42
```

## Tasks

### `affinity task get <taskUrl>`

```bash
affinity task get https://api.affinity.co/tasks/person-merges/123
```

### `affinity task wait <taskUrl>`

```bash
affinity task wait https://api.affinity.co/tasks/person-merges/123 --timeout 120
```
