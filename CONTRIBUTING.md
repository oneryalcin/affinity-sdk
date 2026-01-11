## Contributing

Thanks for your interest in contributing!

### Development setup

- Create a virtual environment (e.g. `python -m venv .venv`) and activate it.
- Install the project in editable mode with dev dependencies:

```bash
python -m pip install -e ".[dev]"
```

### Testing

Run the test suite with:

```bash
pytest
```

#### Test file naming convention

Test files follow these naming patterns:

| Pattern | Use for | Examples |
|---------|---------|----------|
| `test_cli_<topic>.py` | CLI command tests | `test_cli_company_get.py`, `test_cli_error_rendering.py` |
| `test_services_<service>.py` | Service layer tests | `test_services_persons_companies_additional_coverage.py` |
| `test_<feature>.py` | Feature/model tests | `test_models.py`, `test_pagination_iterators.py` |
| `test_http_client_*.py` | HTTP client tests | `test_http_client_additional_coverage.py` |
| `test_v1_only_*.py` | V1 API-specific tests | `test_v1_only_services_additional_coverage.py` |
| `test_integration_*.py` | Integration/smoke tests | `test_integration_smoke.py` |

For coverage gap tests, append `_additional_coverage` or `_remaining_coverage` to the base name.

### CLI Development

If you're working on CLI commands, please review the [CLI Development Guide](docs/cli-development-guide.md) for:
- Standard command structure and patterns
- Model serialization best practices
- Testing CLI commands
- Common pitfalls and troubleshooting

### Quality checks

Before opening a PR, please run:

```bash
ruff format .
ruff check .
mypy affinity
pytest
```

### Pre-commit

We recommend enabling pre-commit hooks:

```bash
pre-commit install
```

### MCP Plugin Development

The MCP server (built on the `xaffinity` CLI) is also available as a Claude Code plugin. For standalone MCP server usage, see the [MCP documentation](https://yaniv-golan.github.io/affinity-sdk/latest/mcp/).

The plugin is distributed via the repository's own marketplace (`.claude-plugin/marketplace.json`). The plugin source files live in `mcp/` but must be assembled into `mcp/.claude-plugin/` before publishing.

#### Building the plugin

```bash
cd mcp
make plugin
```

This copies the MCP server files (`xaffinity-mcp.sh`, `tools/`, `prompts/`, etc.) into `.claude-plugin/`. The copied files are git-ignored.

#### CI validation

The `mcp-plugin` job in `.github/workflows/ci.yml` automatically builds and validates the plugin structure on every push/PR.

### Releasing (maintainers)

This repo uses PyPI trusted publishing (OIDC) via `.github/workflows/release.yml`.

Releases are triggered automatically when version files change on `main`.

#### SDK Release steps

1. Update version in `pyproject.toml` and add release notes to `CHANGELOG.md`.
2. Run quality checks locally:

```bash
ruff format --check .
ruff check .
mypy affinity
pytest
```

3. Commit and push to `main` (or merge a PR):

```bash
git checkout main
git pull --ff-only
# Make version changes
git add pyproject.toml CHANGELOG.md
git commit -m "Release v0.9.1"
git push origin main
```

The release workflow will:
- Detect the version change
- Build and publish to PyPI
- Create a GitHub release
- Create and push the `vX.Y.Z` tag

#### MCP Plugin Release steps

1. Update `mcp/VERSION` and `mcp/CHANGELOG.md`
2. Run pre-commit (syncs plugin.json and server.meta.json)
3. Commit and push to `main`

The release workflow will:
- Detect the version change
- Build the plugin and MCPB bundle
- Create a GitHub release
- Create and push the `mcp-vX.Y.Z` tag

#### Manual tag release

You can also trigger releases via tags:

```bash
# SDK
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z

# MCP
git tag -a mcp-vX.Y.Z -m "MCP vX.Y.Z" && git push origin mcp-vX.Y.Z
```

Notes:
- The workflow enforces `vX.Y.Z` == `pyproject.toml` version
- MCP tags use `mcp-v*` prefix
- No PyPI API tokens are stored in GitHub; publishing relies on trusted publisher configuration
