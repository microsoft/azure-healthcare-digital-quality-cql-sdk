# Development

`cql-sdk` uses **uv** as its canonical developer workflow.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## First-time setup

```bash
./scripts/bootstrap.sh           # or scripts\bootstrap.ps1 on Windows
```

Or manually:

```bash
uv sync --extra dev --extra test
```

## Common commands

| Task                 | Command                                 |
|----------------------|-----------------------------------------|
| Lint                 | `uv run ruff check .`                   |
| Format               | `uv run ruff format .`                  |
| Type-check           | `uv run mypy`                           |
| Base tests           | `uv run pytest -m "not spark"`          |
| Spark tests          | `uv sync --extra spark && uv run pytest -m spark` |
| Build distributions  | `uv build`                              |
| Run CLI              | `uv run cql-sdk --help`                 |

## Test markers

- `unit` — fast, isolated (default)
- `integration` — end-to-end ELM loading / invocation
- `spark` — requires `pyspark` (only runs with the `spark` extra)

## Project layout

See [architecture.md](architecture.md).

## Adding a new operator

1. Add the callable in `cql_sdk/runtime/operators.py`.
2. Register it in `register_builtins`.
3. Add a unit test in `tests/unit/test_runtime_operators.py`.
4. Update `docs/public-api.md` if you're exposing a new public surface.
