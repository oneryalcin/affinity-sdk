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
