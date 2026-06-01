# Bootstrap the cql-sdk dev environment with uv (Windows PowerShell).
$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. Install from https://docs.astral.sh/uv/"
    exit 1
}

uv python install 3.12
uv sync --extra dev --extra test

Write-Host "Environment ready. Try:"
Write-Host "  uv run cql-sdk --version"
Write-Host "  uv run pytest -m 'not spark'"
