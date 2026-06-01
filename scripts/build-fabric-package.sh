#!/usr/bin/env bash
# Build a Microsoft Fabric upload bundle for cql-sdk.
#
# Produces dist/fabric/ containing:
#   - cql_sdk-<version>-py3-none-any.whl   (upload as a Custom library)
#   - environment.yml                      (upload under External repositories)
#   - README.txt                           (short upload instructions)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. See scripts/bootstrap.sh." >&2
    exit 1
fi

echo "==> Building wheel + sdist with uv..."
uv build

wheel="$(ls -t dist/ms_cql_sdk-*-py3-none-any.whl 2>/dev/null | head -n1 || true)"
if [[ -z "$wheel" ]]; then
    echo "Wheel not found in dist/." >&2
    exit 1
fi

out="$root/dist/fabric"
rm -rf "$out"
mkdir -p "$out"

cp "$wheel" "$out/"
cp "$root/fabric/environment.yml" "$out/"

wheel_name="$(basename "$wheel")"
cat > "$out/README.txt" <<EOF
ms-cql-sdk Microsoft Fabric upload bundle
==========================================

Files:
  ${wheel_name}   -> upload as a Custom library (.whl)
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
EOF

echo ""
echo "Fabric bundle ready at: $out"
ls -lh "$out"
