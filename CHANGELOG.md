# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
