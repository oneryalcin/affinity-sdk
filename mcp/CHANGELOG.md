# MCP Server Changelog

All notable changes to the xaffinity MCP server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
