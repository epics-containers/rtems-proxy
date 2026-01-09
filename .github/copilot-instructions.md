# GitHub Copilot Instructions for rtems-proxy

## Development Environment

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and task running.

## Running Tests and Checks

Always use `uv` to run tox commands:

```bash
# Run all checks in parallel
uv run tox -p

# Run specific environment
uv run tox -e type-checking
uv run tox -e tests
uv run tox -e pre-commit
```

## Type Checking

- Run type checking with: `uv run pyright src tests`
- Or via tox: `uv run tox -e type-checking`
- Always fix type errors before committing

## Installing Dependencies

```bash
# Install all dependencies including dev dependencies
uv sync --group dev
```

## Code Style

- This project uses `ruff` for linting and formatting
- Run `uv run tox -e pre-commit` to check formatting
- Pre-commit hooks will auto-format code

## Important Notes

- Do NOT run `tox` directly - always use `uv run tox`
- Do NOT run `pytest` or `pyright` directly - use `uv run` prefix or tox environments
- All external tools (pytest, pyright, pre-commit) are configured in `pyproject.toml` with `allowlist_externals`
