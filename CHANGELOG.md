# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added
- Inbound webhook parsing helpers: `parse_webhook(...)`, `dispatch_webhook(...)`, and `BodyRegistry`.
- CLI: `affinity company get` (id/URL/resolver selectors) with `--all-fields` and `--expand lists|list-entries`.
- CLI: `--max-results` and `--all` controls for pagination and expansions (where supported).
- File downloads: `client.files.download_stream_with_info(...)` exposes headers/filename/size alongside streamed bytes.

### Changed
- `FieldValueType` is now V2-first and string-based (e.g. `dropdown-multi`, `ranked-dropdown`, `interaction`), and `affinity list view` shows readable `valueType` values.
- CLI: human/table output renders dict-shaped results as sections/tables (no JSON-looking panels) and hides pagination mechanics in expanded sections.
- CLI: `--json` output now uses section-keyed `data` and `meta.pagination` (e.g. `data.lists`, `meta.pagination.lists.nextUrl`); pagination may be omitted when `--max-results` truncates mid-page to avoid unsafe resume tokens.

## 0.2.0 - 2025-12-17

### Added
- Initial public release.
- `client.files.download_stream(...)` and `client.files.download_to(...)` for chunked file downloads.
- `client.files.upload_path(...)` and `client.files.upload_bytes(...)` for ergonomic uploads.
- `client.files.all(...)` / `client.files.iter(...)` for auto-pagination over files.

### Changed
- File downloads now follow redirects without forwarding credentials and use the standard retry/diagnostics policy.
- `client.files.list(...)` and `client.files.upload(...)` now require exactly one of `person_id`, `organization_id`, or `opportunity_id` (per API contract).
