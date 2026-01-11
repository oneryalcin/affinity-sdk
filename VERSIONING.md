# Versioning Policy

This document defines how versions are managed across the affinity-api-x repository.

## Overview

| Component | Version Source | Versioning |
|-----------|----------------|------------|
| SDK + CLI | `pyproject.toml` | Single source of truth, SemVer |
| SDK Plugin | Auto-synced | Matches SDK version |
| CLI Plugin | Auto-synced | Matches SDK version |
| MCP Server | `mcp/VERSION` | Independent, declares CLI compatibility |

## Semantic Versioning Rules

We follow [SemVer 2.0.0](https://semver.org/). Given version `MAJOR.MINOR.PATCH`:

### When to Bump MAJOR (breaking change)
- Removing or renaming a public SDK class/method
- Changing CLI command names or required arguments
- Changing JSON output structure in incompatible ways
- Removing CLI flags or options

### When to Bump MINOR (new feature, backwards-compatible)
- Adding new SDK classes/methods
- Adding new CLI commands or optional flags
- Adding new fields to JSON output (additive)
- Performance improvements with no API changes

### When to Bump PATCH (bug fix, backwards-compatible)
- Fixing bugs without changing the API
- Documentation improvements
- Internal refactoring with no external impact

## Pre-1.0 Versioning (Current State)

**SDK is currently at 0.x.y** — per [SemVer spec item 4](https://semver.org/#spec-item-4):
> *"Major version zero (0.y.z) is for initial development. Anything MAY change at any time."*

This means:
- MINOR bumps (0.6 → 0.7) MAY include breaking changes
- PATCH bumps (0.6.5 → 0.6.6) should be backwards-compatible
- MCP must track CLI minor version for compatibility

## CLI Changes That Affect MCP

The MCP server shells out to CLI commands. These changes require MCP updates:

| CLI Change | MCP Impact | Action Required |
|------------|------------|-----------------|
| New command added | None | Optional: add MCP tool |
| New optional flag | None | Optional: use new flag |
| JSON output field added | None | Backwards-compatible |
| JSON output field removed | **Breaking** | Update MCP, bump COMPATIBILITY |
| JSON output structure changed | **Breaking** | Update MCP, bump COMPATIBILITY |
| Command renamed | **Breaking** | Update MCP, bump COMPATIBILITY |
| Required flag added | **Breaking** | Update MCP, bump COMPATIBILITY |

## How to Release

Releases are triggered automatically when version files are updated on `main`.

### How Release Detection Works

The release detection workflow compares the current version in version files against existing release tags:

1. **After CI passes** on `main`, the release detection workflow runs
2. It reads the SDK version from `pyproject.toml` and MCP version from `mcp/VERSION`
3. It checks if release tags exist:
   - SDK: checks for `v{version}` tag (e.g., `v0.9.2`)
   - MCP: checks for `mcp-v{version}` tag (e.g., `mcp-v1.7.6`)
4. If no tag exists for the current version, it triggers the release workflow via `workflow_dispatch` API

The release workflows are triggered via GitHub's workflow_dispatch API (not reusable workflows). This enables:
- **PyPI attestations**: Full provenance attestation support for all releases
- **GITHUB_TOKEN**: No PATs or GitHub Apps required
- **Tag creation post-publish**: Tags are created after successful PyPI publish (SDK) or GitHub release (MCP)

This approach is robust regardless of how many commits are pushed together, squash merges, rebases, or any other git workflow.

### SDK Release

1. Update version in `pyproject.toml`
2. Run pre-commit (syncs plugin versions automatically)
3. Update `CHANGELOG.md` with changes
4. If CLI output changed: check MCP compatibility
5. Commit and push to `main` (or merge PR)
6. **Release runs automatically** — tag created post-release

SDK releases include MCPB bundles (built from the same commit) for convenience, so users don't need to find separate MCP releases.

### MCP Release

1. Update `mcp/VERSION`
2. Update `mcp/CHANGELOG.md`
3. If CLI requirements changed: update `mcp/COMPATIBILITY`
4. Run pre-commit (syncs plugin.json and server.meta.json automatically)
5. Commit and push to `main` (or merge PR)
6. **Release runs automatically** — tag created post-release

### Manual Tag Release

You can also trigger releases via tags:

```bash
# SDK
git tag -a v0.9.1 -m "v0.9.1" && git push origin v0.9.1

# MCP
git tag -a mcp-v1.7.6 -m "MCP v1.7.6" && git push origin mcp-v1.7.6
```

## Tag Naming

| Component | Tag Pattern | Example |
|-----------|-------------|---------|
| SDK | `vX.Y.Z` | `v0.9.0` |
| MCP | `mcp-vX.Y.Z` | `mcp-v1.7.5` |

## Testing MCP Compatibility

Before releasing a CLI change that modifies JSON output:

```bash
# 1. Build and install the new CLI locally
pip install -e .

# 2. Run MCP tools manually to verify they still work
cd mcp
./xaffinity-mcp.sh validate

# 3. Test specific tools
source lib/common.sh
run_xaffinity_readonly person ls --query "test" --output json --quiet
```

## Version File Locations

| File | Purpose | Updated By |
|------|---------|------------|
| `pyproject.toml` | SDK/CLI version | Manual |
| `plugins/affinity-sdk/.claude-plugin/plugin.json` | Plugin version | Pre-commit hook |
| `plugins/xaffinity-cli/.claude-plugin/plugin.json` | Plugin version | Pre-commit hook |
| `mcp/VERSION` | MCP distribution version | Manual |
| `mcp/server.d/server.meta.json` | MCP server metadata | Pre-commit hook |
| `mcp/.claude-plugin/plugin.json` | MCP plugin version | Pre-commit hook |
| `mcp/COMPATIBILITY` | CLI version requirements | Manual |
| `mcp/mcpb.conf` | MCPB bundle config | Manual (version from VERSION) |
| `mcp/mcp-bash.lock` | MCP-bash framework version + commit hash | Manual |

## MCP-Bash Framework Pinning

The MCP server depends on the mcp-bash-framework. Version and commit hash are pinned in `mcp/mcp-bash.lock`.

### When to Update

```bash
# 1. Get the new version's commit hash
git ls-remote https://github.com/yaniv-golan/mcp-bash-framework.git vX.Y.Z

# 2. Update mcp/mcp-bash.lock with both values

# 3. Update mcp/CHANGELOG.md
```

## Release Checklist

### SDK Release
- [ ] Version bumped in `pyproject.toml`
- [ ] Pre-commit ran (plugin versions synced)
- [ ] `CHANGELOG.md` updated
- [ ] If CLI output changed: MCP tested and COMPATIBILITY checked
- [ ] Changes merged to `main`
- [ ] Verify release workflow completed successfully

### MCP Release
- [ ] Version bumped in `mcp/VERSION`
- [ ] `mcp/CHANGELOG.md` updated
- [ ] If CLI requirements changed: `mcp/COMPATIBILITY` verified
- [ ] Pre-commit ran (syncs plugin.json and server.meta.json)
- [ ] Changes merged to `main`
- [ ] Verify release workflow completed successfully
