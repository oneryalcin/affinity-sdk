# Integration Tests

These tests run against a live Affinity sandbox environment to verify SDK functionality with real API calls.

## Setup

1. Create `.sandbox.env` in the project root:
   ```
   AFFINITY_API_KEY=your_sandbox_api_key
   ```

2. Ensure your API key is for a **sandbox instance** (tenant name must end with "sandbox").

## Safety Features

Integration tests have multiple safety layers:

| Layer | Protection |
|-------|-----------|
| **CI/CD skip** | Skipped by default via `-m 'not integration'` in pytest addopts |
| **Env gate** | Skip if `.sandbox.env` not found |
| **Sandbox-only** | Abort if tenant name doesn't end with "sandbox" |
| **Cleanup** | Write tests clean up all created data |

## Running Tests

### Via pytest (Recommended)

```bash
# Run all integration tests
pytest -m integration

# Run only read tests (safe, no side effects)
pytest -m integration -k reads

# Run only write tests
pytest -m integration -k writes

# Run with verbose output
pytest -m integration -v

# Run full write suite (slow, comprehensive)
pytest -m "integration and slow"
```

### Via standalone script (Interactive)

The write test script can also be run directly with interactive prompts:

```bash
# Interactive run with confirmation prompt
python tests/integration/test_sdk_writes.py

# Include beta endpoint tests
python tests/integration/test_sdk_writes.py --include-beta

# Clean up orphan test data from previous failed runs
python tests/integration/test_sdk_writes.py --cleanup-orphans
```

## Test Modules

| Module | Description | Side Effects |
|--------|-------------|--------------|
| `test_sdk_reads.py` | Read-only SDK API tests | None |
| `test_sdk_writes.py` | SDK write tests (standalone script) | Creates/deletes test data |
| `test_sdk_writes_runner.py` | Pytest wrapper for SDK write tests | Creates/deletes test data |
| `test_cli_writes.py` | CLI write workflow tests | Creates/deletes test data |
| `test_query_parity_integration.py` | Query-list export parity tests | None (read-only) |
| `setup_query_parity_data.py` | Setup script for query parity tests | Creates test data once |
| `conftest.py` | Shared fixtures (sandbox client, API key) | None |

## What's Tested

### Read Tests (`test_sdk_reads.py`)

| Group | APIs Tested |
|-------|------------|
| Auth | `whoami()` |
| Persons | `list()`, `get()`, `iter()` |
| Companies | `list()`, `get()`, `iter()` |
| Lists | `list()`, `iter()`, `entries().iter()` |
| Fields | `list()` |
| Opportunities | `list()`, `get()`, `iter()` |
| Notes | `list()`, `get()` |
| Interactions | `list()` for emails and meetings |
| Reminders | `list()` |
| Webhooks | `list()` |
| Field Values | `list()` with person/company filters |

### SDK Write Tests (`test_sdk_writes.py`)

| Group | Tests |
|-------|-------|
| 1. Core CRUD | Person and Company create/read/update/delete |
| 2. Lists | List creation, person/company list entry operations |
| 3. Opportunities | Opportunity CRUD with list membership |
| 4. Fields | Global and list-specific field operations, batch updates |
| 5. Notes & Reminders | Note CRUD on all entity types, reminder scheduling |
| 6. Interactions | Meeting interaction create/update/delete |
| 7. Files | File upload (bytes and path), metadata retrieval |
| 8. Webhooks | Webhook create/update/delete |
| 9. Beta | Person and company merge (requires `--include-beta`) |

### CLI Write Tests (`test_cli_writes.py`)

Targeted tests for CLI write workflows that combine multiple operations:

| Test Class | Workflow |
|------------|----------|
| `TestPersonCRUDWorkflow` | Person create → get → update → delete |
| `TestCompanyCRUDWorkflow` | Company create → get → update → delete |
| `TestNoteCRUDWorkflow` | Create person → attach note → update → delete |
| `TestListEntryWorkflow` | Create person → add to list → get entry → delete |
| `TestReminderCRUDWorkflow` | Create person → create reminder → update → delete |
| `TestCLIOutputFormats` | Verify JSON output structure for create/error |

CLI tests use `CLI_INTEGRATION_TEST_` prefix for test data identification.

### Query Parity Tests (`test_query_parity_integration.py`)

Tests query-list export parity (related: `docs/internal/query-list-export-parity-plan.md`).

**Setup required (one time):**
```bash
python tests/integration/setup_query_parity_data.py
```

**Run tests:**
```bash
pytest tests/integration/test_query_parity_integration.py -m integration -v
```

| Test Class | What's Tested |
|------------|---------------|
| `TestQueryListEntriesBasics` | Query by listName/listId, select fields |
| `TestQueryListEntriesIncludes` | Include persons, companies, interactions |
| `TestQueryListEntriesExpand` | Expand interactionDates, unreplied |
| `TestQueryIncludeAndExpand` | Combining include and expand |
| `TestQueryListExportParity` | Same counts, IDs, field values as list export |
| `TestQueryOutputFormats` | JSON and markdown output |
| `TestQueryDryRun` | Execution plan preview |
| `TestQueryPersons` | Person queries with include/expand |
| `TestQueryCompanies` | Company queries with include/expand |
| `TestQueryEdgeCases` | Empty results, compound filters |

Query parity tests use `QUERY_PARITY_TEST_` prefix for test data identification.

## Notes

- **Lists cannot be deleted** via the API, so test lists will remain in your sandbox
- **V1→V2 eventual consistency**: Tests include appropriate delays and retries to handle the API's eventual consistency between V1 (writes) and V2 (reads)
- **File deletion** is not supported by the API; uploaded test files will remain
- **Test data prefix**: SDK write tests use `SDK_WRITE_TEST_` prefix, CLI tests use `CLI_INTEGRATION_TEST_`

## Troubleshooting

### Tests are skipped

```
SKIPPED: Integration tests require .sandbox.env file with AFFINITY_API_KEY
```

Create `.sandbox.env` in the project root with your sandbox API key.

### "Not a sandbox" error

```
FAILED: Integration tests require a SANDBOX instance. Tenant 'My Company' does not end with 'sandbox'.
```

Your API key is for a production instance. Get an API key from a sandbox instance.

### Running in CI

Integration tests are skipped by default in CI. To run them:

```yaml
# GitHub Actions example
- name: Run integration tests
  env:
    AFFINITY_API_KEY: ${{ secrets.SANDBOX_API_KEY }}
  run: |
    echo "AFFINITY_API_KEY=$AFFINITY_API_KEY" > .sandbox.env
    pytest -m integration
```
