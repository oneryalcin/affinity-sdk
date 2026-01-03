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

#### Releasing the plugin

Plugin releases use a separate tag format (`plugin-vX.Y.Z`):

```bash
cd mcp
make plugin                    # Build the plugin
git tag -a plugin-v1.0.1 -m "Plugin v1.0.1"
git push origin plugin-v1.0.1
```

The `.github/workflows/plugin-release.yml` workflow creates a GitHub Release with the plugin archive.

### Releasing (maintainers)

This repo uses PyPI trusted publishing (OIDC) via `.github/workflows/release.yml`.

#### SDK Release steps

1. Update version in `pyproject.toml` and add release notes (e.g., `CHANGELOG.md`).
2. Run quality checks locally:

```bash
ruff format --check .
ruff check .
mypy affinity
pytest
```

3. Create an annotated tag from `main` (the release workflow rejects tags not on `main`):

```bash
git checkout main
git pull --ff-only
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Notes:
- The workflow enforces `vX.Y.Z` == `pyproject.toml` version.
- No PyPI API tokens are stored in GitHub; publishing relies on trusted publisher configuration in PyPI.
