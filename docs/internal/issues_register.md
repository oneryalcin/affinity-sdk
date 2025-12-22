# Internal Issues and Gaps Register (Open, Partial, or Needs Investigation)

Date: 2025-12-22

Scope:
- Consolidated from docs/internal (excluding archive).
- Includes Open, Partially Implemented, Needs Investigation, Manual Review, and Intentional Omission items.
- Resolved items are intentionally omitted to keep this focused on actionable work.

Priority definitions:
- P0: Release blocker or correctness/security risk.
- P1: High priority missing capability or material DX risk.
- P2: Medium priority gap or significant maintainability/test risk.
- P3: Low priority or polish.
- P4: Research or backlog candidates (not committed work).

Status keywords:
- Open, Partially Implemented, Needs Investigation, Manual Review, Intentional Omission.

## P0 - Release Blockers

None currently.

## P1 - High Priority

### 2. ~~[P1] Webhook authenticity verification is not implemented (parsing only)~~

**Status:** Resolved (documented as not available)

**Summary:** ~~Inbound webhook helpers parse payloads but do not verify authenticity or replay protection beyond timestamps.~~

**Resolution:** After thorough investigation of official Affinity V1 API documentation, **Affinity does NOT provide cryptographic signature verification for webhooks**. There is no HMAC header, signing secret, or other mechanism documented. The SDK now:

1. Clearly documents this limitation with a warning banner in `docs/public/guides/webhooks.md`
2. Provides comprehensive defense-in-depth guidance (secret URL paths, HTTPS, request validation, replay protection via `sent_at`, IP allowlisting, dedupe patterns)
3. Includes an improved FastAPI example demonstrating all security best practices
4. The existing `parse_webhook()` helper already supports `max_age_seconds` for replay protection

**Evidence:**
- Official V1 API docs (`docs/internal/affinity_api_docs_v1.md` lines 4809-5070) document webhooks extensively but contain zero mention of signatures, HMAC, or authentication headers
- V2 API has no webhook support (webhooks are V1-only)
- External sources claiming signature support (affinitylicensing GitHub) were for a completely different company's product

**Changes:**
- `docs/public/guides/webhooks.md` - Updated with clear "No signature verification available" warning and comprehensive defense-in-depth guidance

## P2 - Medium Priority

### 3. [P2] PersonService.resolve() only inspects the first page and has no resolve_all

**Status:** Open

**Summary:** Person resolution checks only page 1 (page_size=10), which can return false negatives for name or email matching.

**Details:**
- The resolver calls V1 search and then filters client-side, but only inspects the first page.
- There is no resolve_all helper for persons.

**Evidence:**
- `affinity/services/persons.py` resolve logic uses a single search page.

**Suggested fix:**
- Add `resolve_all(...)` for persons with explicit ambiguity handling.
- Consider paging beyond the first page when resolving by name or email, with clear cost/behavior documentation.

### 4. [P2] Manual JSON payload construction for V1 create/update persists in some services

**Status:** Partially Implemented

**Summary:** Some V1 services manually assemble JSON payloads instead of using Pydantic model_dump, increasing drift risk.

**Details:**
- Manual payload construction is error-prone and duplicates model logic.
- Pydantic already defines request models; we should use `model_dump(by_alias=True, exclude_unset=True)` to keep payloads aligned.
- Some services (e.g., opportunities) already use `model_dump()`, but others (e.g., persons, v1_only) still use manual construction.

**Evidence:**
- `affinity/services/opportunities.py` uses `model_dump(by_alias=True, exclude_none=True)` correctly.
- Manual payload construction persists in V1 write paths such as `affinity/services/persons.py` and `affinity/services/v1_only.py`.

**Suggested fix:**
- Replace remaining manual payload building with `model_dump(by_alias=True, exclude_unset=True)` where feasible.
- Preserve any required v1 naming translations in a small, explicit adapter layer.

### 5. [P2] Sync/async service duplication remains a maintainability risk

**Status:** Partially Implemented

**Summary:** Retry logic is shared, but most service methods still have duplicated sync/async implementations.

**Details:**
- Large method duplication increases risk of divergent behavior over time.
- The code review recommends centralizing logic in async methods with sync wrappers.

**Evidence:**
- Similar method bodies across `affinity/services/*.py` for sync and async variants.

**Suggested fix:**
- Refactor to a shared core implementation (async-first or helper functions) and thin sync wrappers.
- Ensure docstrings and tests cover parity across both surfaces.

### 6. [P2] OpenAPI validation skip lists can mask schema changes

**Status:** Open

**Summary:** Hardcoded skip lists can hide new schema coverage or drift.

**Details:**
- `KNOWN_EXTENSIONS` and `V1_ONLY_MODELS` can hide cases where a model is now present in the schema.
- This creates false negatives in validation.

**Evidence:**
- `tools/validate_openapi_models.py` defines `KNOWN_EXTENSIONS` and `V1_ONLY_MODELS` and skips before schema lookup.

**Suggested fix:**
- If a skipped model exists in the schema, fail or emit a warning.
- Narrow skip behavior to only when the schema component is truly missing.
- Distinguish "allowed extension" vs "schema drift" in output.

### 7. [P2] OpenAPI validation does not run on PRs (scheduled only)

**Status:** Open

**Summary:** Schema drift can land in PRs without detection until a scheduled job runs.

**Details:**
- OpenAPI validation is scheduled weekly and is not part of PR CI.
- There are no live contract tests beyond optional integration smoke tests.

**Evidence:**
- `.github/workflows/openapi-validation.yml` runs on schedule only.
- `tests/test_integration_smoke.py` exists but is optional.

**Suggested fix:**
- Add a PR CI job to run `tools/validate_openapi_models.py` in offline/pinned mode.
- Optionally keep the scheduled job for upstream drift detection.

### 8. [P2] Bulk list-entry helpers are missing

**Status:** Open

**Summary:** Only single-item add/delete methods exist for list entries.

**Details:**
- Common workflows require bulk add/remove; today users must write loops.
- This increases the risk of partial failures and retry issues.

**Evidence:**
- `affinity/services/lists.py` exposes `add_person/add_company/add_opportunity` and `delete(entry_id)` only.

**Suggested fix:**
- Add SDK bulk helpers (e.g., `add_people([...])`, `add_companies([...])`, `delete_many([...])`) with clear partial failure reporting.

### 9. [P2] CLI is missing `opportunity files dump`

**Status:** Open

**Summary:** The CLI supports file dump for person/company but not opportunity.

**Details:**
- The file-dump helper exists, but there is no opportunity command wired to it.
- This blocks parity with person/company file workflows in the CLI.

**Evidence:**
- `affinity/cli/commands/opportunity_cmds.py` lacks `files dump`.
- `_entity_files_dump.dump_entity_files_bundle` exists for reuse.

**Suggested fix:**
- Add `affinity opportunity files dump` that reuses `_entity_files_dump` helpers.
- Add a CLI test to verify wiring and parameters.

### 10. [P2] CLI integration tests missing for key commands

**Status:** Partially Implemented

**Summary:** Core CLI commands lack direct invocation tests (search, list, list-entry writes, file dumps).

**Details:**
- Tests exist for company/person get, opportunity commands, and note CRUD.
- Direct CLI invocation tests for company/person search, list ls, list-entry write, and file-dump commands are missing.

**Evidence:**
- CLI test coverage exists in `tests/test_cli_company_get.py` and related files, but not for the audit-called-out commands.

**Suggested fix:**
- Add `click.testing.CliRunner` tests for search/list/list-entry write/file-dump paths.
- Stub `CLIContext.get_client()` to avoid network calls.

### 11. [P2] Company get expansions still use private HTTP client for pagination

**Status:** Open

**Summary:** `affinity company get --expand ...` still calls `client._http.get/get_url` because the public service API does not accept cursor/limit for those expansions.

**Details:**
- The CLI needs resume-aware pagination, but the service surface does not expose cursor for expansions.

**Evidence:**
- `affinity/cli/commands/company_cmds.py` uses `client._http.get/get_url` for expansion pagination.

**Suggested fix:**
- Add cursor/limit support on relevant service helpers and update CLI to use public APIs.

### 12. [P2] `/persons/fields` endpoint shape discrepancy needs investigation

**Status:** Resolved (decision)

**Summary:** V2 field metadata endpoints are the public surface; V1 array shape is not exposed. V1-only writes require numeric field IDs and reject unmappable IDs.

**Details:**
- SDK uses V2 `/v2/persons/fields` and expects `{data, pagination}`; V1 `/persons/fields` is not part of the public surface.
- V1-only write paths require numeric IDs derived from `field-<digits>` and reject enriched/relationship-intelligence IDs with no V1 equivalent.
- No bridging/normalization is needed unless the SDK decides to expose V1 field endpoints.

**Evidence:**
- V1 docs show array response: `docs/internal/affinity_api_docs_v1.md` (`GET /persons/fields`).
- V2 docs show `{data, pagination}` envelope: `docs/internal/affinity_api_docs_v2.md` (`GET /v2/persons/fields`).
- SDK uses V2 path: `affinity/services/persons.py`.
- V1-only writes use numeric conversion: `affinity/services/v1_only.py`, `affinity/models/types.py`.

**Resolution:**
- Keep V2-only reads and do not expose V1 `/persons/fields`.
- Treat non-`field-<digits>` IDs as unmappable for V1 writes (existing behavior).

### 13. [P2] Requirement traceability marker missing for FR-002

**Status:** Open

**Summary:** There is no explicit test tagged with `@pytest.mark.req('FR-002')`.

**Details:**
- Requirements tracking expects explicit markers for traceability.
- FR-002 is V2-first architecture; it lacks a direct test marker.

**Evidence:**
- No `@pytest.mark.req('FR-002')` found in `tests/`.

**Suggested fix:**
- Add at least one requirement-tagged test covering FR-002 behavior.

### 14. [P2] Manual-review requirements are still pending signoff

**Status:** Manual Review

**Summary:** Several requirements explicitly require manual review or documentation signoff.

**Details:**
- NFR-005: Hide implementation details (users never specify API versions, URLs, or internal HTTP clients).
- TR-006/TR-008: Dependency audits and transport validation.
- DX-001/DX-002: Intuitive API design and predictable behavior.
- DX-003/DX-009: Documentation coverage and async lifecycle guidance.
- DX-005: Error message quality review.
- These items require explicit signoff to claim requirements compliance.

**Evidence:**
- Manual-review status is noted in requirements tracking and handoff notes.

**Suggested fix:**
- Perform a structured code and docs review against each acceptance criteria.
- Record signoff (or create follow-up tasks) for each requirement.

## P3 - Low Priority / Polish

### 15. [P3] CLI human output lacks explicit presentation hints and action-style output

**Status:** Open

**Summary:** Human output is still type-shape driven and cannot be overridden by commands.

**Details:**
- The renderer should accept a presentation hint (auto, table, kv, action, text).
- Action commands should render a short success sentence plus a small key/value table.

**Evidence:**
- `affinity/cli/render.py` uses shape-driven rendering only.
- `affinity/cli/runner.py` does not carry a presentation hint in result metadata.

**Suggested fix:**
- Add a `Presentation` hint to `CommandOutput` and plumb it through to the renderer.
- Implement action-style rendering and update dump/export/upload commands to set it.

### 16. [P3] CLI human-output Phase 2 rollout is incomplete

**Status:** Partially Implemented

**Summary:** Phase 0 and Phase 1 are done, but Phase 2 needs to migrate remaining commands.

**Details:**
- Migrate remaining renderer special cases to the generic section renderer.
- Apply expansion pagination normalization and human-mode hiding across other commands.

**Evidence:**
- The rollout plan calls for Phase 2 migration of remaining commands and special cases.

**Suggested fix:**
- Audit remaining renderer special cases and migrate them to the generic renderer.
- Ensure pagination metadata is consistently stored under `meta.pagination`.

### 17. [P3] CLI URL redaction has some overlap with SDK helpers

**Status:** Partially Implemented

**Summary:** The CLI has its own redaction helpers for `--trace` that partially overlap with SDK URL redaction.

**Details:**
- The SDK has extensive URL redaction in `affinity/clients/http.py` (`_redact_url`, `_redact_external_url`, `_sanitize_hook_url`).
- The CLI uses `set_redaction_api_key` from logging and has separate sanitization in `affinity/cli/context.py`.
- There is some overlap but the SDK does most of the heavy lifting.

**Evidence:**
- CLI redaction wiring in `affinity/cli/context.py` (lines 47, 190, 376-418, 547-600).
- SDK URL redaction in `affinity/clients/http.py` (extensive `_redact_*` and `_sanitize_*` functions).

**Suggested fix:**
- Consider consolidating CLI redaction to fully delegate to SDK helpers where possible.
- Low priority since the SDK already handles most redaction.

### 18. [P3] CLI `--trace` does not use SDK `on_event`

**Status:** Open

**Summary:** The CLI uses request/response/error hooks directly instead of the higher-level event stream.

**Details:**
- If `on_event` is the intended user-facing hook surface, the CLI should demonstrate it.

**Evidence:**
- CLI trace wiring uses request/response/error hooks in `affinity/cli/main.py` and `affinity/cli/context.py`.

**Suggested fix:**
- Route `--trace` through the SDK `on_event` stream and let the SDK handle redaction and formatting.

### 19. [P3] CLI JSON emission is implemented in multiple places

**Status:** Open

**Summary:** The runner and renderer both have JSON emission paths, risking divergence.

**Details:**
- Output shape may drift if multiple serializers are maintained.

**Evidence:**
- JSON emission logic appears in both `affinity/cli/runner.py` and `affinity/cli/render.py`.

**Suggested fix:**
- Keep a single JSON emission path and route all output through it.

### 20. [P3] Name/ID resolution helpers still live in the CLI

**Status:** Partially Implemented

**Summary:** Some resolution helpers (saved views, fields) remain CLI-specific and could be SDK utilities.

**Details:**
- List resolution has SDK helpers, but other selectors remain in CLI glue.

**Evidence:**
- CLI resolution helpers live in `affinity/cli/resolve.py`.

**Suggested fix:**
- Move remaining resolution helpers into SDK services where appropriate and reuse in CLI.

### 21. [P3] CLI spec features missing: --color, CSV/YAML output, keychain storage

**Status:** Open (explicitly deferred in spec)

**Summary:** The spec lists several deferred features that are still unimplemented.

**Details:**
- Global `--color` flag.
- Non-JSON/table output formats (CSV/YAML).
- OS keychain storage for API keys.
- These were explicitly listed as deferred and need an explicit keep-or-implement decision.

**Evidence:**
- CLI spec notes these as not implemented.

**Suggested fix:**
- Implement if desired, or explicitly keep deferred with a rationale and non-goal statement.

### 22. [P3] Migration guide is missing from public docs

**Status:** Open

**Summary:** There is no migration guide for users moving from raw API usage or older SDKs.

**Details:**
- Docs nav lacks a migration entry.
- Guidance is scattered across other guides.

**Evidence:**
- `mkdocs.yml` has no migration guide entry.

**Suggested fix:**
- Add `docs/public/guides/migration.md` and link it in the nav.

### 23. [P3] Getting Started Phase 2 and Phase 3 items are still open

**Status:** Open

**Summary:** The onboarding ladder is missing advanced steps and recipes.

**Details (Phase 2):**
- Add a first real workflow walkthrough (list companies -> filter -> inspect fields).
- Add a common pitfalls section (typed IDs, fields.requested, v1/v2 write differences).

**Details (Phase 3):**
- Add recipes for common jobs: list-entry create/update, resolve helpers, task polling.

**Evidence:**
- `docs/public/getting-started.md` contains Phase 1 only.

**Suggested fix:**
- Implement the Phase 2 and Phase 3 content and link from the onboarding ladder.

### 24. [P3] README is long and mixes quickstart with deep reference

**Status:** Open

**Summary:** The README is too long and duplicates docs content.

**Details:**
- Long README content makes it harder to find the minimal path to success.

**Evidence:**
- `README.md` is ~494 lines with extended examples and reference material.

**Suggested fix:**
- Keep README focused on installation and a short quickstart.
- Move deep examples to docs and link to them.

### 25. [P3] Notebook examples are missing

**Status:** Open

**Summary:** There are no notebook-based examples for interactive users.

**Details:**
- The repo has Python examples only (`examples/*.py`).

**Evidence:**
- No `examples/notebooks/` directory exists.

**Suggested fix:**
- Add 1 to 2 notebooks using `Affinity.from_env()` and link them in docs.

### 26. [P3] No load/stress benchmark harness

**Status:** Open

**Summary:** There is no optional benchmarking harness to catch throughput regressions.

**Details:**
- Current tests are unit/behavioral with mocked HTTP plus optional smoke tests.

**Evidence:**
- No benchmark tool exists under `tools/` or `tests/`.

**Suggested fix:**
- Add a lightweight benchmark harness (pytest-benchmark or `tools/bench.py`).

### 27. [P3] Paginated list response caching is absent

**Status:** Open

**Summary:** Only field metadata responses are cached; list pages are not.

**Details:**
- Repeated list reads can cause avoidable API traffic for CLI and notebooks.

**Evidence:**
- `affinity/services/lists.py` list methods do not set cache keys.

**Suggested fix:**
- Add optional caching for paginated GETs with short TTL and opt-in flag.

### 28. [P3] External docs reference pages need refinement

**Status:** Open (optional)

**Summary:** The reference section is broad and could be more external-user focused.

**Details:**
- Large reference pages (e.g., `affinity.models`) are hard to scan.

**Evidence:**
- `docs/public/reference/` pages are broad and lightly curated.

**Suggested fix:**
- Add entrypoint-focused reference pages and hide private helpers in mkdocstrings settings.

### 29. [P3] Webhook CLI commands are intentionally omitted

**Status:** Intentional Omission

**Summary:** The CLI does not expose webhook commands, despite SDK support.

**Details:**
- This may be acceptable, but it should be an explicit product decision.

**Evidence:**
- No webhook CLI commands exist under `affinity/cli/commands/`.

**Suggested fix:**
- Decide whether to keep this omission or add minimal `webhook ls/get/create/delete` commands.

### 30. [P3] Opportunity add_person/remove_person helpers are missing

**Status:** Open

**Summary:** OpportunityService lacks convenience helpers for add/remove person or company operations.

**Details:**
- The V1 update API is replace-only, so helper methods would need to read current IDs and write back a merged list.
- These helpers are useful but non-atomic and must warn about concurrent update risks.

**Evidence:**
- `affinity/services/opportunities.py` exposes `update()` and `get_details()`, but no add/remove helpers.

**Suggested fix:**
- Add `add_person/add_company/remove_person/remove_company` helpers that call `get_details()` + `update()`.
- Document that they are read-modify-write and not atomic.

## P4 - Research / Backlog Candidates (Not Committed)

### 31. [P4] Async concurrency guardrails for quota safety

**Status:** Backlog

**Summary:** Add an optional global concurrency limit for async requests.

**Details:**
- Prevent accidental bursts (e.g., large `asyncio.gather` calls).
- Complement rate-limit handling by reducing pressure before 429s.

**Evidence:**
- Old repo uses a quota-aware async client with a semaphore (`../affinity-crm-api/src/new_affinity_client/http.py`).

**Suggested fix:**
- Add an opt-in concurrency limit in `ClientConfig` and enforce in `AsyncHTTPClient`.

### 32. [P4] Standard pagination controls (`max_items`, `max_pages`, timeout)

**Status:** Backlog

**Summary:** Provide consistent safety rails across iterators and list operations.

**Details:**
- Allow callers to cap work deterministically without manual page accounting.

**Evidence:**
- Pagination controls exist in the old repo (`../affinity-crm-api/README_pagination.md`).

**Suggested fix:**
- Add optional caps to iterator constructors or `all()` methods, not via decorators.

### 33. [P4] Test-time "no live network" guardrails

**Status:** Backlog

**Summary:** Prevent accidental live network calls during unit tests.

**Details:**
- Add a hard fail if any real network call occurs unless explicitly allowed.

**Evidence:**
- Proposed in the older prototype repo as a safety net (`../affinity-api-2`).

**Suggested fix:**
- Add a test harness or transport guard that blocks outbound HTTP by default.

### 34. [P4] Typed option bundles for parameter-heavy endpoints

**Status:** Backlog

**Summary:** Use typed parameter bundles instead of ever-expanding method signatures.

**Details:**
- Improves IDE hints and future-proofs query parameter evolution.

**Evidence:**
- TypedDict-based options are used in the old repo (`../affinity-crm-api/docs/typed_parameters.md`).

**Suggested fix:**
- Introduce small Params models or TypedDicts for list/search endpoints.

### 35. [P4] Structured concurrency helpers for bulk operations

**Status:** Backlog

**Summary:** Provide TaskGroup-based helpers for SDK bulk methods.

**Details:**
- Centralizes cancellation, error aggregation, and backpressure patterns.

**Evidence:**
- Structured concurrency helpers appear in old repo notes (`../affinity-crm-api`).

**Suggested fix:**
- Add a small, opinionated concurrency helper used by future bulk APIs.

### 36. [P4] Operation routing diagnostics (v1 vs v2)

**Status:** Backlog

**Summary:** Surface which API version handled a request for debugging.

**Details:**
- Helps explain behavior differences and routing decisions.

**Evidence:**
- "Smart client" diagnostic idea appears in the prototype repo review.

**Suggested fix:**
- Emit routing info in diagnostics or hook payloads without changing method signatures.

### 37. [P4] Pluggable cache protocol for future expansion

**Status:** Backlog

**Summary:** Define a cache interface for future Redis/memcached integration.

**Details:**
- Current caching is limited to metadata; future expansion may need a stable protocol.

**Evidence:**
- Old repo defines a cache protocol and decorators (`../affinity-crm-api`).

**Suggested fix:**
- Add a minimal cache protocol while keeping cache keys explicit and testable.

### 38. [P4] Generate sync services from async source to reduce duplication

**Status:** Backlog

**Summary:** Reduce sync/async duplication via generated sync wrappers.

**Details:**
- The prototype repo suggests using async as the source of truth.

**Evidence:**
- Proposed in the prototype review (`../affinity-api-2`).

**Suggested fix:**
- Evaluate feasibility of code generation or wrapper patterns for sync services.

### 39. [P4] Threadpool + requests fallback (only if httpx issues are reproducible)

**Status:** Backlog

**Summary:** Consider a fallback HTTP backend only if real httpx interoperability bugs surface.

**Details:**
- Avoid adding complexity unless a reproducible issue exists.

**Evidence:**
- Mentioned in prototype repo notes as a last-resort workaround.

**Suggested fix:**
- Keep as a contingency plan; do not implement without a concrete repro.

### 40. [P4] Avoid decorator-heavy stacks for pagination/circuit breakers

**Status:** Backlog (anti-pattern warning)

**Summary:** Old repo postmortems show decorator stacks can break async generators and sync wrappers.

**Details:**
- The recommendation is to keep control flow explicit to avoid brittle wrappers.

**Evidence:**
- Old repo postmortem notes on decorator stacks (`../affinity-crm-api/DECORATOR_FIX.md`).

**Suggested fix:**
- Prefer explicit control flow and small helpers over stacked decorators.
