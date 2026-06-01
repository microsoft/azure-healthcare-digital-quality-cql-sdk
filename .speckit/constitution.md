# cql-sdk Constitution

> A small set of non-negotiable rules that govern how this repository
> evolves. These rules take precedence over convenience. Changes to this
> document require explicit review.

## 1. Purpose

`cql-sdk` is a **modular Python SDK for Clinical Quality Language (CQL)**
and its compiled form ELM. It provides:

- A pure-Python core for ELM loading, type handling, runtime context,
  operators, and invocation.
- Optional adapters for FHIR and PySpark / Microsoft Fabric.
- Packaging primitives for CQL/ELM artifacts.
- A Typer-based CLI (`cql-sdk`).

The SDK is inspired by the layering of the Firely C# CQL SDK but is
implemented idiomatically for Python and modern data platforms.

## 2. Core principles

These principles are binding on every contribution:

1. **Pure-Python core.** Nothing in
   [`cql_sdk.abstractions`](../src/cql_sdk/abstractions/),
   [`cql_sdk.elm`](../src/cql_sdk/elm/),
   [`cql_sdk.runtime`](../src/cql_sdk/runtime/),
   [`cql_sdk.compiler`](../src/cql_sdk/compiler/),
   [`cql_sdk.invocation`](../src/cql_sdk/invocation/), or
   [`cql_sdk.packaging`](../src/cql_sdk/packaging/) may import
   `pyspark` or any FHIR model library.
2. **Optional integrations are opt-in.** Spark (`pyspark`) is only
   importable from [`cql_sdk.spark`](../src/cql_sdk/spark/). FHIR model
   libraries are only referenced from [`cql_sdk.fhir`](../src/cql_sdk/fhir/).
   Both are installed via optional extras, never by default.
3. **Invocation is the preferred public entry point.** End users consume
   [`cql_sdk.api`](../src/cql_sdk/api.py) and
   [`cql_sdk.invocation.toolkit.InvocationToolkit`](../src/cql_sdk/invocation/toolkit.py).
   Low-level operator or planner internals are **not** the recommended
   user path and may change between minor versions.
4. **Pre-generated ELM is a first-class workflow.** Normal execution must
   not require Java or a CQL-to-ELM toolchain. Authoring / regeneration
   tools remain a separate, optional workflow.
5. **Explicit layering.** Modules only depend downward. The dependency
   direction is:
   `api → invocation → { compiler, runtime, elm } → abstractions`, with
   `fhir`, `spark`, `packaging`, and `cli` depending on the layers above
   them but never on each other.
6. **Small, cohesive modules.** A module does one thing, exposes a narrow
   surface, and has a docstring explaining its role.
7. **Typed, documented, testable.** Every public function/class has type
   hints and a docstring. Mypy runs in strict mode on `src/`.
   Every new behavior ships with a pytest test.
8. **Protocols over base classes** for seams (operators, terminology,
   data source, type conversion, packaging, invocation). Concrete
   implementations live in the relevant feature package.

## 3. Public API stability

The following surface is **public** and governed by semver:

- [`cql_sdk.api`](../src/cql_sdk/api.py)
- [`cql_sdk.invocation.toolkit.InvocationToolkit`](../src/cql_sdk/invocation/toolkit.py)
- [`cql_sdk.runtime.context.RuntimeContext`](../src/cql_sdk/runtime/context.py)
- [`cql_sdk.abstractions`](../src/cql_sdk/abstractions/__init__.py) protocols
- [`cql_sdk.compiler.cql_to_elm`](../src/cql_sdk/compiler/cql_to_elm/__init__.py) (CQL → ELM front end, added in 0.2.0)
- [`cql_sdk.fhir`](../src/cql_sdk/fhir/__init__.py) (when `fhir` extra installed)
- [`cql_sdk.spark`](../src/cql_sdk/spark/__init__.py) (when `spark` extra installed)
- [`cql_sdk.packaging`](../src/cql_sdk/packaging/__init__.py)
- The `cql-sdk` console script and its documented subcommands

Everything else — in particular the rest of `cql_sdk.compiler.*` (planner,
expression builder, type manager, bindings) and the concrete operator
implementations in `cql_sdk.runtime.operators` — is **internal** and may
change without notice.

## 4. Dependency rules

- Runtime dependencies in [`pyproject.toml`](../pyproject.toml) `project.dependencies`
  must be small, widely-used, and justified. Current runtime set:
  `typer`, `rich`, `pydantic`, `python-dateutil`.
- Optional extras: `fhir`, `spark`, `dev`, `test`, `docs`. Extras never
  graduate to base dependencies without an RFC.
- The base wheel installed into a clean environment must satisfy both:
  - `import cql_sdk` and `import cql_sdk.cli.main` succeed.
  - `import pyspark` **fails**. CI enforces this in
    [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## 5. Tooling

- **Python**: 3.12+ (pinned in [`.python-version`](../.python-version)).
- **Packaging**: `pyproject.toml` only, Hatchling backend, `src/` layout.
- **Environment**: [uv](https://docs.astral.sh/uv/) is the canonical
  developer workflow. Every common task has a `uv run …` or Makefile
  equivalent (see [docs/development.md](../docs/development.md)).
- **Lint**: `ruff` (config in `pyproject.toml`, line length 100, rules
  `E, F, W, I, B, UP, SIM, RUF, D, TID`).
- **Type check**: `mypy --strict` on `src/`.
- **Tests**: `pytest` with markers `unit`, `integration`, `spark`. The
  default `pytest` run excludes `spark`.
- **CI**: GitHub Actions in
  [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs lint,
  type, base tests, build, and the Spark-freeness check. A separate,
  gated job installs `--extra spark` and runs `-m spark`.

## 6. Contribution discipline

- Changes must keep ruff and mypy clean.
- Every code change ships with a test; bug fixes add a regression test.
- Breaking changes to any symbol listed in §3 require a major-version
  bump and a migration note in the release notes.
- Adding a new operator follows the playbook in
  [docs/development.md](../docs/development.md): register in
  `runtime/operators.py` → unit test → update `docs/public-api.md` only
  if a new public symbol is exposed.
- New optional dependencies belong to an extra, not the base.

## 7. Non-goals (explicit)

- A full, production-complete CQL spec implementation is **not** the
  goal of the initial releases. The runtime intentionally implements a
  thin vertical slice with clear extension points.
- The SDK does not ship clinical content. Measure / library artifacts
  are distributed separately; see [docs/packaging.md](../docs/packaging.md).
- The SDK does not bind to a single FHIR Python model library.
  `cql_sdk.fhir` provides adapter seams; concrete models are pluggable.

## 8. Amendments

This constitution is amended by pull request with an explicit changelog
entry. Rule removals or weakenings require sign-off from a repository
maintainer and a note in [specification.md](specification.md) explaining
how the affected behavior changes.
