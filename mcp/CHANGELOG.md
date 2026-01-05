# MCP Server Changelog

All notable changes to the xaffinity MCP server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-01-06

### Changed
- **Skill**: Added CLI Gateway tools documentation (discover-commands, execute-read-command, execute-write-command).
- **Skill**: Added destructive command confirmation flow (look up, ask, wait, execute with `confirm: true`).
- **Skill**: Clarified conversation-based confirmation works with all MCP clients regardless of elicitation support.

## [1.1.0] - 2026-01-05

### Added
- **CLI Gateway tools**: 3 new tools enabling full CLI access with minimal token overhead
  - `discover-commands`: Search CLI commands by keyword, returns compact text or JSON format
  - `execute-read-command`: Execute read-only CLI commands with retry and truncation support
  - `execute-write-command`: Execute write CLI commands with destructive command confirmation
- **Pre-generated command registry**: `mcp/.registry/commands.json` for zero-latency discovery
  - Registry validated at startup and in CI
  - Generator script: `tools/generate_cli_commands_registry.py` (requires CLI `--help --json` support)
- **CLI Gateway validation library**: `lib/cli-gateway.sh` with shared validation functions
  - `validate_registry()`: Verify registry exists and has valid structure
  - `validate_command()`: Check command exists in registry with correct category
  - `validate_argv()`: Validate arguments against per-command schema
  - `is_destructive()`: Check if command is destructive (from registry metadata)
  - `find_similar_command()`: Fuzzy matching for "Did you mean" suggestions on typos
- **Proactive output limiting**: Auto-inject `--limit` for commands that support it
- **CI validation**: Registry structure validation in GitHub Actions
- **API key health check**: Warns at startup if API key is not configured or invalid
- **Policy enforcement**: Runtime policy controls via environment variables
  - `AFFINITY_MCP_READ_ONLY=1`: Restrict to read-only operations
  - `AFFINITY_MCP_DISABLE_DESTRUCTIVE=1`: Block destructive commands entirely
- **Metrics logging**: `log_metric()` helper for structured metrics output
- **Post-execution cancellation**: Check `mcp_is_cancelled` after CLI execution

### Changed
- `lib/common.sh`: Added `jq_tool` wrapper, `REGISTRY_FILE` constant, and `log_metric()` helper
- `server.d/policy.sh`: Added CLI Gateway tools to read/write tool lists
- `server.d/env.sh`: Environment passthrough for policy variables via `MCPBASH_TOOL_ENV_ALLOWLIST`
- `confirmation_required` error now includes `example` field showing how to confirm
- `command_not_found` error now includes "Did you mean" hint for similar commands

### CLI Prerequisites (Implemented)
- CLI now supports `--help --json` for machine-readable help output
- All destructive commands (`*delete`) now support `--yes` flag for non-interactive execution
- Registry generated from live CLI via `tools/generate_cli_commands_registry.py`

## [1.0.5] - 2026-01-03

### Fixed
- **Typed argument helpers**: Fixed syntax for `mcp_args_bool` and `mcp_args_int` - require `--default`, `--min`, `--max` keyword arguments
- **Progress reporting**: Fixed `((current_step++))` failing with `set -e` when counter is 0 - use pre-increment `((++current_step))` instead
- **get-workflow-view**: Fixed CLI command (`list-entry export` → `list export`), positional arg for list ID, and `--saved-view` flag

## [1.0.4] - 2026-01-03

### Added
- **Progress reporting**: Long-running tools now report progress via mcp-bash SDK
  - `get-entity-dossier`: Reports progress for each data collection step
  - `get-relationship-insights`: Reports progress for connection analysis
  - `find-entities`: Reports progress for parallel search operations
  - Supports client cancellation via `mcp_is_cancelled` checks
- **Tool annotations**: All tools now include MCP 2025-03-26 annotations
  - `readOnlyHint`: Distinguishes read vs write operations
  - `destructiveHint`: Write tools marked as non-destructive (updates, not deletes)
  - `openWorldHint`: All tools interact with external Affinity API
  - `idempotentHint`: Status/field update tools are idempotent
- **Health checks**: Added `server.d/health-checks.sh` for startup validation
  - Verifies `xaffinity` CLI is available
- **Typed argument helpers**: Tools now use mcp-bash typed argument helpers
  - `mcp_args_bool` for boolean parameters with proper defaults
  - `mcp_args_int` for integer parameters with min/max validation
- **JSON tool compatibility**: All tools now use `MCPBASH_JSON_TOOL_BIN` (jq or gojq)
- **Automatic retry**: CLI calls use `mcp_with_retry` for transient failure handling (3 attempts, exponential backoff)
- **Debug mode**: Comprehensive logging for debugging MCP tool invocations
  - Set `MCPBASH_LOG_LEVEL=debug` or `XAFFINITY_DEBUG=true` to enable
  - Logs CLI command execution with exit codes and output sizes
  - Logs tool invocation parameters and completion stats
  - Auto-enables `MCPBASH_TOOL_STDERR_CAPTURE` in debug mode
- **lib/common.sh**: Added `xaffinity_log_*` helpers wrapping mcp-bash SDK logging
- **server.d/env.sh**: Documented debug mode configuration with examples

### Changed
- Tools now use structured logging via mcp-bash SDK (`mcp_log_debug`, `mcp_log_info`, etc.)
- CLI wrapper functions log command execution in debug mode (args redacted for security)
- Multi-step tools now use `mcp_progress` for visibility into operation status

## [1.0.3] - 2026-01-03

### Fixed
- **get-entity-dossier**: Fixed `relationship-strength get` (doesn't exist) → `relationship-strength ls --external-id`
- **get-entity-dossier**: Fixed entity data extraction path (`.data` → `.data.person`/`.data.company`/`.data.opportunity`)
- **get-entity-dossier**: Fixed interaction fetching - now queries all types (Affinity API limitation)
- **get-relationship-insights**: Fixed relationship-strength command usage
- **get-interactions**: Now queries all interaction types (email, meeting, call, chat-message) when no type specified, due to Affinity API limitation
- **get-interactions**: Fixed null participant handling in jq transformation
- **lib/common.sh**: Fixed `--quiet` flag positioning (must be global option before subcommand)

### Added
- Test harness using `mcp-bash run-tool` with dry-run validation and live API tests
- `.env.test` configuration pattern for private test data (gitignored)

## [1.0.2] - 2026-01-03

### Added
- **MCPB bundle support**: One-click installation via `.mcpb` bundles for Claude Desktop and other MCPB-compatible clients
- New `make mcpb` target to build MCPB bundles using mcp-bash-framework v0.9.0
- `mcpb.conf` configuration file for bundle metadata

### Changed
- Upgraded to mcp-bash-framework v0.9.0 (from 0.8.4)
- Updated Makefile with separate targets for MCPB bundles and Claude Code plugin ZIP

## [1.0.1] - 2026-01-03

### Changed
- ZIP-based plugin distribution for Claude Code compatibility
- Added COMPATIBILITY file for CLI version requirements
- Added FRAMEWORK_VERSION file for mcp-bash-framework version tracking
- Runtime CLI version validation on server startup

### Fixed
- Plugin bundle now includes all required MCP server files

## [1.0.0] - 2025-01-03

### Added
- Initial stable release of xaffinity MCP server
- Complete tool suite for Affinity CRM operations:
  - `find-entities`: Search for persons, organizations, and opportunities
  - `get-entity-details`: Retrieve detailed entity information with field values
  - `get-list-entries`: Query list entries with filtering and pagination
  - `export-list`: Export list data to CSV format
  - `workflow-analyze-entries`: Analyze list entries for workflow automation
  - `workflow-update-field`: Update field values on list entries
- Workflow prompts for guided CRM operations
- Session caching for improved performance
- Readonly mode support for safe operations

### CLI Compatibility
- Requires xaffinity CLI >= 0.6.0, < 1.0.0
- Uses JSON output format with `.data` wrapper
- Depends on `--session-cache`, `--readonly`, and `--output json` flags
