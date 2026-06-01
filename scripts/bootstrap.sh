#!/usr/bin/env bash
# Bootstrap the cql-sdk dev environment with uv.
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install from https://docs.astral.sh/uv/" >&2
    exit 1
fi

uv python install 3.12
uv sync --extra dev --extra test

echo "Environment ready. Try:"
echo "  uv run cql-sdk --version"
echo "  uv run pytest -m 'not spark'"
