# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.9.9 - 2026-01-14

### Added
- CLI: `query` command now supports advanced relationship filtering:
  - `all` quantifier: Filter where all related items match a condition (e.g., find persons where all their companies have ".com" domains)
  - `none` quantifier: Filter where no related items match a condition (e.g., find persons with no spam interactions)
  - `exists` subquery: Filter where at least one related item exists, optionally matching a condition (e.g., find persons who have email interactions)
  - `_count` pseudo-field: Filter by count of related items (e.g., `"path": "companies._count", "op": "gte", "value": 2`)
  - Available relationship paths: persons→companies/opportunities/interactions/notes/listEntries, companies→persons/opportunities/interactions/notes/listEntries, opportunities→persons/companies/interactions
  - Note: These features cause N+1 API calls to fetch relationship data; use `--dry-run` to preview

### Changed (Breaking)
- CLI: Renamed relationship `"people"` to `"persons"` for consistency with entity type names:
  - Query `include`: `{"from": "companies", "include": ["people"]}` → use `["persons"]`
  - CLI `--expand`: `xaffinity company get <id> --expand people` → use `--expand persons`
  - JSON output: `data.people` → `data.persons`

### Fixed
- CLI: Query engine no longer silently passes all records for `all`, `none`, and `_count` filters. Previously these were placeholder implementations that returned `True` for all records, causing incorrect query results. (Bug #15)

## 0.9.8 - 2026-01-12

### Fixed
- CLI: `query` command now correctly fetches all records before applying filter, sort, or aggregate operations. Previously, limits were applied during fetch which caused incorrect results:
  - With filters: Empty results when matching records were beyond the limit position
  - With sort + limit: Random N records sorted instead of actual top N
  - With aggregate: Inaccurate counts/sums computed on partial data

## 0.9.7 - 2026-01-12

### Fixed
- CI: Smoke test now correctly installs CLI extras before testing CLI import

## 0.9.6 - 2026-01-12

### Added
- CLI: `listEntries` queries now include convenience aliases: `listEntryId`, `entityId`, `entityName`, `entityType`. These intuitive field names work in both `select` and `where` clauses.
- CLI: `listEntries` records now always include a `fields` key (defaults to `{}` if no custom fields).

### Changed
- CLI: Query projection now includes null values for explicitly selected fields. Previously, `select: ["entityName", "fields.Status"]` would return `{}` if Status was null; now returns `{"entityName": "Acme", "fields": {"Status": null}}`.

## 0.9.5 - 2026-01-12

### Added
- CLI: New `--output`/`-o` option supporting multiple formats: `json`, `jsonl`, `markdown`, `toon`, `csv`, `table` (default).
  - `markdown`: GitHub-flavored markdown tables, best for LLM analysis and comprehension
  - `toon`: Token-Optimized Object Notation, 30-60% fewer tokens than JSON for large datasets
  - `jsonl`: JSON Lines format, one object per line for streaming workflows
  - Example: `xaffinity person ls --output markdown`, `xaffinity query -o toon`
  - Existing `--csv` and `--json` flags continue to work as before.

### Changed
- CLI: `to_cell()` now extracts "text" from dropdown/multi-select fields instead of JSON-serializing the full dict. This makes CSV and other tabular outputs human-readable for dropdown values.

### Fixed
- CLI: `query` command with `limit` now correctly returns results when combined with client-side filters (like `has_any` on multi-select fields). Previously, the limit was applied during fetch before filtering, causing empty results when the first N records didn't match the filter criteria.

## 0.9.4 - 2026-01-12

### Added
- CLI: `query` command now supports `has_any` and `has_all` operators for multi-select field filtering.
- SDK/CLI: Filter parser now supports V2 API comparison operators: `>`, `>=`, `<`, `<=` for numeric/date comparisons.
- SDK/CLI: Filter parser now supports word-based operator aliases for LLM/human clarity:
  - `contains`, `starts_with`, `ends_with` (string matching)
  - `gt`, `gte`, `lt`, `lte` (numeric/date comparisons)
  - `is null`, `is not null`, `is empty` (null/empty checks)
- SDK/CLI: Filter parser now supports collection bracket syntax `[A, B, C]` with operators:
  - `in [A, B]` - value is one of the listed values
  - `between [1, 10]` - value is in range (inclusive)
  - `has_any [A, B]` - array field contains any of the values
  - `has_all [A, B]` - array field contains all of the values
  - `contains_any [A, B]` - substring match for any term
  - `contains_all [A, B]` - substring match for all terms
  - `= [A, B]` - set equality (array has exactly these elements)
  - `=~ [A, B]` - V2 API collection contains (array contains all elements)

### Fixed
- CLI: `query` command now correctly filters on multi-select dropdown fields (like "Team Member"). The `eq` operator checks array membership for scalar values and set equality for array values. Previously, these queries returned 0 results due to strict equality comparison.
- SDK/CLI: `list export --filter` now correctly matches multi-select dropdown fields. The `=`, `!=`, and `=~` operators now handle array values properly. Also fixes extraction of text values from multi-select dropdown API responses.
- SDK/CLI: Fixed `=^` (starts_with) and `=$` (ends_with) operators which were broken due to tokenizer ordering issue.

### Improved
- SDK/CLI: Filter parser now provides helpful hints for common mistakes:
  - Multi-word field names: suggests quoting (`"Team Member"`)
  - Multi-word values: suggests quoting (`"Intro Meeting"`)
  - SQL keywords (`AND`, `OR`): suggests correct symbols (`&`, `|`)
  - Double equals (`==`): suggests single `=`

## 0.9.3 - 2026-01-11

### Changed
- CI: SDK releases now include MCPB bundle and plugin ZIP for convenience.
- CI: Enabled PyPI attestations via workflow_dispatch API trigger.

## 0.9.2 - 2026-01-11

### Fixed
- SDK: `AsyncListEntryService.pages()` now supports `progress_callback` parameter (sync/async parity fix).

### Changed
- **BREAKING**: CLI: `interaction ls` JSON output restructured for consistency:
  - `.data.interactions` → `.data` (direct array)
  - `.data.metadata.totalRows` → `.meta.summary.totalRows`
  - `.data.metadata.dateRange` → `.meta.summary.dateRange`
  - `.data.metadata.typeStats` → `.meta.summary.typeBreakdown`
- **BREAKING**: CLI: `note ls` JSON output restructured for consistency:
  - `.data.notes` → `.data` (direct array)
  - Pagination: `.data.notes.nextCursor` → `.meta.pagination.nextCursor`
- **BREAKING**: CLI: `query` JSON output (with `--include-meta`) restructured for consistency:
  - `.meta.recordCount` → `.meta.summary.totalRows`
  - Included entity counts now in `.meta.summary.includedCounts`
- CLI: Standardized `ResultSummary` footer rendering across all commands (displays row counts, date ranges, type breakdowns as compact footer text instead of tables).

## 0.9.1 - 2026-01-11

### Added
- CLI: `query` command now validates entity queryability and provides clear error messages for unsupported entities.
- CLI: `query` command resolves field names to IDs automatically (e.g., `"field": "Status"` works alongside `"fieldId": 123`).

### Fixed
- CLI: `query` for `listEntries` entity now correctly requires `listId` filter.
- CLI: `query` relationship definitions now correctly set `requires_n_plus_1` flag for proper query planning.

## 0.9.0 - 2026-01-11

### Added
- CLI: New `query` command for structured JSON queries with complex filtering, includes, aggregations, and sorting. Use `--dry-run` to preview execution plans. Supports entities: persons, companies, opportunities, listEntries, interactions, notes.
- MCP: New `query` tool for complex data queries via JSON query language. Supports filtering (AND/OR/NOT), includes (related entities), aggregations (count/sum/avg/min/max), groupBy, and sorting.
- CLI: `--limit` alias for `--max-results` on `company get`, `person get`, and `opportunity get` commands (consistency with `ls` commands).

### Changed
- CLI: `--list`, `--list-entry-field`, and `--show-list-entry-fields` now auto-imply `--expand list-entries` on `company get` and `person get` commands (improved DX).

## 0.8.6 - 2026-01-10

### Added
- SDK: `PersonService.get_associated_company_ids()` and `get_associated_opportunity_ids()` methods for symmetric association API.
- SDK: `CompanyService.get_associated_opportunity_ids()` method.

## 0.8.5 - 2026-01-10

### Fixed
- CLI/SDK: `FilterParseError` now raised when filter expressions fail to parse (previously silently ignored). Common cause: unquoted multi-word values like `--filter 'Status=Intro Meeting'` must be quoted: `--filter 'Status="Intro Meeting"'`.
- CLI: Pre-commit hook now validates installed CLI version matches `pyproject.toml` before regenerating MCP registry.

## 0.8.4 - 2026-01-10

### Added
- CLI: NDJSON progress output for `interaction ls` multi-type queries (MCP integration).

## 0.8.3 - 2026-01-10

### Added
- CLI: `--limit` alias for `--max-results` on all `ls` commands (LLM-friendly).
- CLI: Option aliases now included in `--help --json` output.

## 0.8.0 - Unreleased

### Changed
- CLI: Renamed `--json` to `--set-json` on `person field`, `company field`, `opportunity field` commands to avoid conflict with global `--json` output flag.
- **BREAKING**: CLI: `--csv FILE` is now `--csv` flag that outputs CSV to stdout. Use shell redirection: `--csv > file.csv`. Applies to `person ls`, `company ls`, `opportunity ls`, `list export`.
- CLI: `--csv` and `--json` are now mutually exclusive (error if both specified).
- CLI: `person ls --query` and `company ls --query` now support `--field` and `--field-type` options via hybrid V1→V2 fetch.
- **BREAKING**: CLI: `interaction ls` date filter parameters renamed for consistency:
  - `--start-time` → `--after`
  - `--end-time` → `--before`
  - Context metadata keys changed: `startTime`/`endTime` → `after`/`before`
  - Note: Interaction object fields (`startTime`/`endTime`) are unchanged
- **BREAKING**: CLI: `interaction ls` now requires `--type` (was optional but API required it).
- CLI: `interaction ls` date range now defaults to all-time when `--days` and `--after` are omitted.
- **BREAKING**: CLI: `interaction ls` removed `--cursor` and `--all` flags (auto-chunking replaces manual pagination).
- **BREAKING**: CLI: `interaction ls` output field renamed `modifiers.type` → `modifiers.types` (now always an array).
- **BREAKING**: CLI: `interaction ls` metadata `chunksProcessed` moved to `typeStats[type].chunksProcessed`.
- **BREAKING**: CLI: Naive datetime strings (without timezone) are now interpreted as **local time** instead of UTC. Use explicit `Z` suffix or offset for UTC. See [datetime-handling guide](https://yaniv-golan.github.io/affinity-sdk/latest/guides/datetime-handling/) for details.
- **BREAKING**: CLI: List entry field commands unified into single `entry field` command:
  - `entry set-field --field F --value V` → `entry field --set F V`
  - `entry set-field --field F --value-json '{...}'` → `entry field --set-json '{"F": ...}'`
  - `entry set-fields --updates-json '{...}'` → `entry field --set-json '{...}'`
  - `entry unset-field --field F` → `entry field --unset F`
  - `entry unset-field --field F --value V` → `entry field --unset-value F V`
  - `entry unset-field --field F --all-values` → `entry field --unset F`
  - Removed: `--field-id` option (field IDs can be passed as FIELD argument directly)
  - **Behavior change:** `--set` on multi-value field now replaces all values (use `--append` to add)

### Added
- CLI: `interaction ls --type` now accepts multiple types (e.g., `--type email --type meeting`).
- CLI: `interaction ls --type all` convenience option fetches all interaction types.
- CLI: `interaction ls` multi-type results sorted by date descending (types interleaved).
- CLI: `interaction ls` metadata includes `typeStats` with per-type counts and chunk info.
- CLI: `interaction ls` auto-chunking for date ranges > 1 year (transparently splits into API-compatible chunks).
- CLI: `interaction ls --days N` convenience flag for "last N days" queries.
- CLI: `interaction ls --csv` and `--csv-bom` flags for CSV export.
- CLI: `interaction ls` metadata in JSON output includes `dateRange`, `typeStats`, `totalRows`.
- SDK: `ListEntryService.from_saved_view()` now accepts `field_ids` and `field_types` parameters.
- CLI: `list export --saved-view` can now be combined with `--field` for server-side filtering with explicit field selection.
- SDK: `ids` parameter added to `PersonService`, `CompanyService`, and `OpportunityService` for batch fetching by ID.
- CLI: `entry field --get FIELD` for reading field values (new functionality).
- CLI: `entry field --append FIELD VALUE` for adding to multi-value fields without replacing.
- CLI: `entry field --unset-value FIELD VALUE` for removing specific value from multi-value field.

### Fixed
- SDK: `FieldValues` now properly parses field arrays from API responses (previously showed `requested=False`).

### Removed
- CLI: `person search` and `company search` commands. Use `person ls --query` and `company ls --query` instead.
- CLI: Removed `entry set-field`, `entry set-fields`, and `entry unset-field` commands (replaced by unified `entry field`).

## 0.7.0 - 2026-01-08

### Added
- CLI: Column limiting for wide table output - tables now auto-limit columns based on terminal width.
- CLI: `--all-columns` flag to show all columns regardless of terminal width.
- CLI: `--max-columns N` flag for fine control over column limits.
- CLI: Real-time filter scanning progress during `list export --filter` shows "Scanning X... (Y matches)".
- CLI: Export summary line after filtered operations (e.g., "Exported 35 rows (filtered from 9,340 scanned) in 2:15").
- CLI: `format_duration()` helper for human-readable time formatting.
- CLI: Rich pager now uses `styles=True` to preserve ANSI colors when paging.
- SDK: `FilterStats` dataclass for tracking scanned/matched counts during filtered pagination.
- SDK: `PaginatedResponse.filter_stats` property exposes filter statistics.

### Fixed
- CLI: JSON progress output no longer appears alongside Rich progress bar (mutual exclusivity enforced).
- SDK: Dropdown field filtering now extracts "text" property from dropdown dicts.

## 0.6.11 - 2026-01-07

### Added
- CLI: Parameter help text (`help`) now included in `--help --json` output.
- CLI: Click.Choice values (`choices`) now included in `--help --json` output.
- CLI: Examples from docstrings now parsed and included in `--help --json` output.

### Changed
- CLI: Improved `--filter` help text with full operator list (`= != =~ =^ =$ > < >= <=`).
- CLI: Improved `--query` help text to clarify V1 fuzzy search vs V2 structured filtering.

## 0.6.10 - 2026-01-06

### Added
- CLI: JSON progress output to stderr when not connected to a TTY (for MCP integration).
- CLI: `@progress_capable` decorator to mark commands supporting progress reporting.
- CLI: Rate-limited progress updates (0.65s interval) with guaranteed 100% completion emission.
- CLI: `progressCapable` field in `--help --json` output for registry generation.
- MCP: `run_xaffinity_with_progress` helper for progress-aware CLI execution.
- MCP: `command_supports_progress` helper to check registry for progress capability.
- MCP: Execute tools now forward CLI progress for `@progress_capable` commands.
- CLI: File upload commands (`person/company/opportunity files upload`) marked as `@progress_capable`.
- MCP: `PROGRESS_MIN_VERSION` in COMPATIBILITY for graceful degradation with older CLIs.
- MCP: `version_gte` helper for portable version comparison (macOS/Linux).
- MCP: CLI version check in `command_supports_progress` (disables progress for CLI < 0.6.10).
- MCP: `XAFFINITY_CLI_VERSION` exported for tool scripts to access CLI version.

### Changed
- MCP: Updated mcp-bash.lock to patched v0.9.3 (commit ee245a7) with progress passthrough fixes.

## 0.6.9 - 2026-01-06

### Changed
- CLI Plugin: Skill now documents destructive command confirmation flow (look up, ask, wait, execute with `--yes`).
- CLI Plugin: Skill lists all destructive commands requiring double confirmation.

## 0.6.8 - 2026-01-05

### Added
- CLI: `@category` and `@destructive` decorators for MCP registry generation.
- CLI: `--help --json` output for machine-readable command documentation.
- CLI: Commands now expose category (read/write/local) and destructive metadata.

## 0.6.7 - 2026-01-03

### Changed
- Docs: Updated all documentation links to use versioned `/latest/` URLs for reliable navigation.

## 0.6.6 - 2026-01-03

### Fixed
- SDK: Regex patterns in `lists.py` and `http.py` were double-escaped, matching literal `\d` instead of digits.

## 0.6.5 - 2026-01-02

_No user-facing changes. Version bump for PyPI release._

## 0.6.4 - 2026-01-02

_No user-facing changes. Version bump for PyPI release._

## 0.6.3 - 2026-01-02

_No user-facing changes. Version bump for PyPI release._

## 0.6.2 - 2026-01-02

### Fixed
- CLI: Added explicit `type=str` to Click arguments for Python 3.13 mypy compatibility.

## 0.6.1 - 2026-01-02

### Changed
- Docs: Separated MCP Server documentation from Claude Code plugins.

## 0.6.0 - 2026-01-02

### Added
- MCP: `read-xaffinity-resource` tool for clients with limited resource support.

### Changed
- Plugins: Restructured into 3-plugin marketplace architecture (affinity-sdk, xaffinity-cli, xaffinity-mcp).
- Docs: Restructured Claude integrations with consistent naming.

### Fixed
- CLI: Improved `setup-key` command UX with Rich styling.
- MCP: Source both `.zprofile` and `.zshrc` in environment wrapper.
- MCP: Parse JSON response correctly for `check-key` output.

## 0.5.1 - 2026-01-01

### Fixed
- Plugins: Consolidated plugin structure and fixed relative paths.

## 0.5.0 - 2026-01-01

### Added
- MCP: Initial xaffinity MCP server as separate Claude Code plugin.
- CLI: Top-level `entry` command group as shorthand for `list entry` (e.g., `xaffinity entry get` instead of `xaffinity list entry get`).
- CLI: `--query` / `-q` flag for `person ls`, `company ls`, and `opportunity ls` to enable free-text search (V1 API).
- CLI: `--company-id` and `--opportunity-id` options for `interaction ls`.
- CLI: `-A` short flag for `--all` on all paginated list commands.
- CLI: `-n` short flag for `--max-results` on all commands with result limits.
- CLI: `-s` short flag for `--page-size` on all pagination commands.
- CLI: `-t` short flag for `--type` on interaction commands.
- CLI: Structured `CommandContext` for all commands.
- SDK: `OpportunityService.search()`, `search_pages()`, `search_all()` methods for V1 opportunity search.
- SDK: Async versions of opportunity search methods in `AsyncOpportunityService`.
- SDK: `InteractionService.list()` now accepts `company_id` and `opportunity_id` parameters.

### Changed
- CLI: `list view` renamed to `list get` for consistency with other entity commands.
- CLI: `--completed/--not-completed` boolean flag pattern for `reminder update` (replaces separate flags).
- CLI: Removed API version mentions from help text (implementation detail).
- CLI: `interaction ls` now requires an entity ID (`--person-id`, `--company-id`, or `--opportunity-id`) and defaults to last 7 days with visible warning (API max: 1 year).
- CLI: Unified `person field`, `company field`, `opportunity field` commands replace `set-field`, `set-fields`, and `unset-field` commands. New syntax: `--set FIELD VALUE`, `--unset FIELD`, `--set-json '{...}'`, `--get FIELD`.
- CLI: Note content separated from metadata in table display.

### Removed
- CLI: `person set-field`, `person set-fields`, `person unset-field` commands (use `person field` instead).
- CLI: `company set-field`, `company set-fields`, `company unset-field` commands (use `company field` instead).
- CLI: `opportunity set-field`, `opportunity set-fields`, `opportunity unset-field` commands (use `opportunity field` instead).

### Fixed
- CLI: Help text formatting - added missing spaces in command examples (~78 instances).
- CLI: Improved `--cursor` help text explaining incompatibility with `--page-size`.
- CLI: Clarified `--csv` help text to indicate it writes to file while stdout format is unchanged.
- CLI: CommandContext validation and test isolation issues.

## 0.4.8 - 2025-12-31

### Added
- CLI: `xaffinity field history` for viewing field value change history.
- CLI: Session caching for pipeline optimization via `AFFINITY_SESSION_CACHE` environment variable.
- CLI: `session start/end/status` commands for managing session cache lifecycle.
- CLI: `--session-cache` and `--no-cache` global flags for cache control.
- CLI: Cache hit/miss visibility with `--trace` flag.
- CLI: `config check-key --json` now includes `pattern` field showing key source.
- SDK: Client-side filtering for list entries (V2 API does not support server-side filtering).

### Changed
- CLI: `--filter` on list entry commands now applies client-side with warning (V2 API limitation).
- CLI: Removed `--opportunity-id` from `list entry add` (opportunities are created atomically via `opportunity create --list-id`).

### Fixed
- SDK: Client-side filter parsing handles whitespace-only and unparseable filters gracefully.
- CLI: `--filter` on list entries now returns proper field values (V2 API format).

## 0.4.0 - 2025-12-30

### Added
- CLI: `config check-key` command to check if an API key is configured (checks environment, .env, and config.toml).
- CLI: `config setup-key` command for secure API key configuration with hidden input, validation, and automatic .gitignore management.
- CLI: `set-field`, `set-fields`, `unset-field` commands for person, company, opportunity, and list entry entities.
- CLI: `list entry get` command with field metadata display.
- CLI: Enhanced `--expand-filter` syntax with OR (`|`), AND (`&`), NOT (`!`), NULL checks (`=*`, `!=*`), and contains (`=~`).
- SDK: `list_entries` field added to `Person` model.
- SDK: Unified filter parser with `parse()` function and `matches()` method for client-side filter evaluation.

### Changed
- CLI: Authentication error hints now reference `config check-key` and `config setup-key` commands.
- CLI: Authentication documentation updated with Quick Setup section.

### Fixed
- CLI: Default `--page-size` reduced from 200 to 100 to match Affinity API limit.
- SDK: Async `merge()` parameter names corrected (`primaryCompanyId`/`duplicateCompanyId`).
- SDK: Cache invalidation added to async create/update/delete in `CompanyService`.

### Removed
- CLI: Deprecated `field-value` and `field-value-changes` command groups removed (use entity-specific field commands instead).
- CLI: Deprecated `update-field` and `batch-update` list entry commands removed (use `set-field`/`set-fields` instead).

## 0.3.0 - 2025-12-30

### Added
- CLI: `xaffinity list export --expand` for exporting list entries with entity field expansion (company/person/opportunity fields).
- CLI: `xaffinity field-value-changes ls` for viewing field value change history.
- CLI: `xaffinity company get` (id/URL/resolver selectors) with `--all-fields` and `--expand lists|list-entries|people`.
- CLI: `xaffinity person get` (id/URL/resolver selectors) with `--all-fields` and `--expand lists|list-entries`.
- CLI: `xaffinity person ls` and `xaffinity company ls` with search flags.
- CLI: `xaffinity opportunity` command group with `ls/get/create/update/delete`.
- CLI: `xaffinity note`, `xaffinity reminder`, and `xaffinity interaction` command groups.
- CLI: `xaffinity file upload` command for file uploads.
- CLI: Write/merge/field operations for list entries.
- CLI: `--max-results` and `--all` controls for pagination and expansions.
- CLI: Progress reporting for all paginated commands.
- CLI: Rate limit visibility via SDK event hook.
- CLI: `--trace` flag for debugging SDK requests.
- SDK: `client.files.download_stream_with_info(...)` exposes headers/filename/size alongside streamed bytes.
- SDK: v1-only company association helpers `get_associated_person_ids(...)` and `get_associated_people(...)`.
- SDK: List-scoped opportunity resolution helpers `resolve(...)` and `resolve_all(...)`.
- SDK: Async parity for company and person services.
- SDK: Async parity for V1-only services.
- SDK: Async list and list entry write helpers.
- SDK: Pagination support for person resolution in `PersonService` and `AsyncPersonService`.
- SDK: `client.clear_cache()` method for cache invalidation.
- SDK: Field value changes service with `client.field_value_changes`.
- SDK: Detailed exception handling for `ConflictError`, `UnsafeUrlError`, and `UnsupportedOperationError`.
- SDK: Webhook `sent_at` timestamp validation.
- SDK: Request pipeline with policies (read-only mode, transport injection).
- SDK: `on_error` hook for error observability.
- Inbound webhook parsing helpers: `parse_webhook(...)`, `dispatch_webhook(...)`, and `BodyRegistry`.
- Claude Code plugin for SDK/CLI documentation and guidance.

### Changed
- CLI: Enum fields now display human-readable names instead of integers (type, status, direction, actionType).
- CLI: Datetimes render in local time with timezone info in column headers.
- CLI: Human/table output renders dict-shaped results as sections/tables (no JSON-looking panels).
- CLI: `--json` output now uses section-keyed `data` and `meta.pagination`.
- CLI: List-entry fields tables default to list-only fields; use `--list-entry-fields-scope all` for full payloads.
- CLI: Domain columns are now linkified in table output.
- CLI: Output only pages when content would scroll.
- `FieldValueType` is now V2-first and string-based (e.g. `dropdown-multi`, `ranked-dropdown`, `interaction`).
- `ListEntry.entity` is now discriminated by `entity_type`.
- Rate limit API unified across sync and async clients.

### Fixed
- SDK: `ListService.get()` now uses V1 API to return correct `list_size`.
- CLI: JSON serialization now handles datetime objects correctly.
- Sync entity file download `deadline_seconds` handling.
- File downloads now use public services for company expansion pagination.

## 0.2.0 - 2025-12-17

### Added
- Initial public release.
- `client.files.download_stream(...)` and `client.files.download_to(...)` for chunked file downloads.
- `client.files.upload_path(...)` and `client.files.upload_bytes(...)` for ergonomic uploads.
- `client.files.all(...)` / `client.files.iter(...)` for auto-pagination over files.

### Changed
- File downloads now follow redirects without forwarding credentials and use the standard retry/diagnostics policy.
- `client.files.list(...)` and `client.files.upload(...)` now require exactly one of `person_id`, `organization_id`, or `opportunity_id` (per API contract).
