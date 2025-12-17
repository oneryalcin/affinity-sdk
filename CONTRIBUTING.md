## Contributing

Thanks for your interest in contributing!

### Development setup

- Create a virtual environment (e.g. `python -m venv .venv`) and activate it.
- Install the project in editable mode with dev dependencies:

```bash
python -m pip install -e ".[dev]"
```

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

### Releasing (maintainers)

This repo uses PyPI trusted publishing (OIDC) via `.github/workflows/release.yml`.

Release steps:

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
