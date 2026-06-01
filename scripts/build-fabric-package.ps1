# Build a Microsoft Fabric upload bundle for cql-sdk (Windows PowerShell).
#
# Produces dist/fabric/ containing:
#   - cql_sdk-<version>-py3-none-any.whl   (upload as a Custom library)
#   - environment.yml                      (upload under External repositories)
#   - README.txt                           (short upload instructions)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "uv is not installed. See scripts/bootstrap.ps1."
        exit 1
    }

    Write-Host "==> Building wheel + sdist with uv..."
    uv build | Out-Host

    $wheel = Get-ChildItem -Path "dist" -Filter "ms_cql_sdk-*-py3-none-any.whl" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $wheel) {
        Write-Error "Wheel not found in dist/."
        exit 1
    }

    $out = Join-Path $root "dist/fabric"
    if (Test-Path $out) { Remove-Item -Recurse -Force $out }
    New-Item -ItemType Directory -Path $out | Out-Null

    Copy-Item $wheel.FullName -Destination $out
    Copy-Item (Join-Path $root "fabric/environment.yml") -Destination $out

    $readme = @"
ms-cql-sdk Microsoft Fabric upload bundle
==========================================

Files:
  $($wheel.Name)   -> upload as a Custom library (.whl)
  environment.yml  -> upload under External repositories (YML editor view)

Steps in the Fabric portal:
  1. Open your workspace and create or open an Environment.
  2. External repositories -> YML editor -> paste environment.yml -> Save.
  3. Custom libraries -> Upload -> select the .whl -> Save.
  4. Publish the environment (Full mode recommended for production).
  5. Attach the environment to your notebook or Spark job definition.

Runtime requirement:
  ms-cql-sdk targets Python 3.12. Use a Fabric Spark runtime that ships
  with Python 3.12 or newer. The Python import name remains `cql_sdk`.
"@
    Set-Content -Path (Join-Path $out "README.txt") -Value $readme -Encoding UTF8

    Write-Host ""
    Write-Host "Fabric bundle ready at: $out"
    Get-ChildItem $out | Format-Table Name, Length
}
finally {
    Pop-Location
}
