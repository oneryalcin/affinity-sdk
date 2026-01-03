---
name: Release
about: Checklist for SDK or MCP releases
---

## Release Type

- [ ] SDK Release (vX.Y.Z)
- [ ] MCP Release (plugin-vX.Y.Z)

## SDK Release Checklist (vX.Y.Z)

- [ ] Version bumped in `pyproject.toml`
- [ ] Plugin versions synced (pre-commit should handle)
- [ ] `CHANGELOG.md` updated with breaking changes noted
- [ ] If CLI output format changed: MCP `COMPATIBILITY` updated
- [ ] Tests pass locally and in CI

## MCP Release Checklist (plugin-vX.Y.Z)

- [ ] Version bumped in `mcp/VERSION`
- [ ] `mcp/.claude-plugin/plugin.json` version updated
- [ ] `mcp/mcpb.conf` MCPB_VERSION updated
- [ ] `mcp/COMPATIBILITY` CLI requirements updated if needed
- [ ] `mcp/CHANGELOG.md` documents CLI compatibility
- [ ] Builds successfully: `cd mcp && make all verify`

## Post-Merge

- [ ] Tag pushed: `git tag vX.Y.Z && git push --tags` (SDK)
- [ ] Tag pushed: `git tag plugin-vX.Y.Z && git push --tags` (MCP)
