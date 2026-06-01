# Packaging

This document covers two distinct concerns:

1. How the **SDK itself** is packaged and distributed.
2. How **CQL/ELM artifacts** (libraries, resources, measures) are packaged
   for downstream consumers.

## 1. SDK packaging

- Build backend: [Hatchling](https://hatch.pypa.io/latest/).
- Single pure-Python wheel for the entire SDK.
- Optional extras keep the base install lean:
  - `fhir` — FHIR model helpers
  - `spark` — `pyspark`
  - `dev`, `test`, `docs`
- `pyproject.toml` is the single source of truth. No `setup.py`.

Build locally:

```bash
uv build            # produces dist/*.whl and dist/*.tar.gz
```

The base install must never pull `pyspark`. CI enforces this by building
and installing the base wheel in a clean environment and asserting that
`import cql_sdk` and `import cql_sdk.cli.main` both succeed.

## 2. CQL/ELM artifact packaging

`cql_sdk.packaging` provides primitives to turn a directory of ELM + JSON
resources into a self-describing *package*:

```python
from pathlib import Path
from cql_sdk.packaging import LibraryPackage

pkg = LibraryPackage.discover(Path("measures/DiabetesHbA1c"))
pkg.write(Path("dist/packages"))
```

The resulting output contains:

- the original `.elm.json` files
- any sibling JSON resources (e.g. FHIR `Library`, `Measure`, value sets)
- a `manifest.json` describing the package, version, and contents

### Why separate from the SDK wheel?

Measure / library artifacts evolve independently of SDK code. Shipping
them as separate packages (wheels, FHIR NPM, zip bundles, etc.) lets
consumers upgrade the engine and the clinical content on different
cadences.

### Writing FHIR Bundles

`cql_sdk.packaging.bundle_writer.write_bundle(resources, path)` emits a
`Bundle` of type `collection` — useful when downstream systems expect a
single JSON document.

## Pre-generated ELM is a first-class workflow

The SDK is designed so **consumers do not need Java or a CQL-to-ELM
toolchain** for normal execution. Authoring / regeneration tools remain
a separate, optional workflow that writes into the same packaging layout.
