# Installing cql-sdk into a Microsoft Fabric environment

This guide packages `cql-sdk` as a custom library and installs it into a
Microsoft Fabric Spark environment, following
[Manage libraries in Fabric environments](https://learn.microsoft.com/en-us/fabric/data-engineering/environment-manage-library).

## 1. Build the Fabric bundle

From the repository root:

```powershell
# Windows
./scripts/build-fabric-package.ps1
```

```bash
# Linux / macOS
./scripts/build-fabric-package.sh
```

This produces [dist/fabric/](../dist/fabric/) with:

- `cql_sdk-<version>-py3-none-any.whl` — the SDK wheel (custom library).
- `environment.yml` — PyPI dependencies for the External repositories tab.
- `README.txt` — quick upload reminder.

The base wheel is pure Python and intentionally does not depend on
`pyspark`; the Fabric Spark runtime provides it.

## 2. Create or open a Fabric environment

In the Fabric portal:

1. Open the workspace that will run the notebooks or Spark job definitions.
2. Create a new **Environment** item (or open an existing one).
3. Select a Spark runtime whose Python version satisfies `>=3.12`
   (`pyproject.toml` requires Python 3.12). Pick a newer Fabric runtime if
   your current default ships an older Python.

## 3. Add the PyPI dependencies (External repositories)

1. Open **External repositories** in the left navigation.
2. Switch to **YML editor view**.
3. Paste the contents of [fabric/environment.yml](../fabric/environment.yml)
   (or upload it directly).
4. Save.

If your workspace blocks public PyPI (Outbound Access Protection or
Private Link), use a private feed instead. Replace the `pip:` block with
either an Azure Artifact Feed connection ID or a `--index-url` pointing at
your private mirror, as described in the Fabric docs.

## 4. Upload the wheel (Custom libraries)

1. Open **Custom libraries** in the left navigation.
2. Click **Upload** and select
   `dist/fabric/cql_sdk-<version>-py3-none-any.whl`.
3. Save.

## 5. Publish and attach

1. Click **Publish**.
   - **Full mode** is recommended for production and Spark job definitions
     (publish takes ~3–6 minutes, sessions start with a stable snapshot).
   - **Quick mode** is fine for iterative notebook development.
2. Attach the environment to your notebook (top bar **Environment** picker)
   or to your Spark job definition.

## 6. Verify

In a notebook cell:

```python
import cql_sdk
from cql_sdk.version import __version__
print("cql-sdk", __version__)
```

For the CLI entry point (notebook shell):

```bash
%sh cql-sdk --version
```

## Updating to a new version

1. Bump `version` in `pyproject.toml`.
2. Re-run the build script.
3. In the Fabric environment, **delete** the previous wheel under Custom
   libraries, upload the new one, and **Publish** again. Direct in-place
   replacement is not supported.

## Optional extras

The wheel respects the optional extras defined in `pyproject.toml`:

- `fhir` — uncomment `fhir.resources>=7.1` in `environment.yml`.
- `spark` — **do not install**; Fabric provides `pyspark`.
- `dev`, `test`, `docs` — not needed in Fabric.
