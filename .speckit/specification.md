# cql-sdk Specification

> Version: 0.2.1 — aligned with [`src/cql_sdk/version.py`](../src/cql_sdk/version.py).
>
> This document specifies the **observable behavior** of the SDK as
> implemented in the current source tree. It is authoritative for
> consumers and kept in lockstep with the code; any change to the
> behaviors below requires a matching source change (and vice versa).
>
> See the [constitution](constitution.md) for the governing rules that
> this specification must satisfy.

---

## 1. Packaging

### 1.1 Distribution

- Distribution name: **`cql-sdk`** (defined in [`pyproject.toml`](../pyproject.toml)).
- Import namespace: **`cql_sdk`**.
- Build backend: Hatchling, single pure-Python wheel, `src/` layout.
- Supported Python: **3.12+** (`requires-python = ">=3.12"`).

### 1.2 Dependencies

| Group            | Contents                                               |
|------------------|--------------------------------------------------------|
| Base (required)  | `typer`, `rich`, `pydantic`, `python-dateutil`         |
| Extra `fhir`     | `fhir.resources`                                       |
| Extra `spark`    | `pyspark`                                              |
| Extra `dev`      | `ruff`, `mypy`, `build`, `pre-commit`                  |
| Extra `test`     | `pytest`, `pytest-cov`, `pytest-xdist`                 |
| Extra `docs`     | `mkdocs`, `mkdocs-material`                            |

Install examples:

```bash
uv sync                              # base only
uv sync --extra fhir                 # + FHIR adapters
uv sync --extra spark                # + Spark adapters (pulls pyspark)
uv sync --extra dev --extra test     # developer environment
```

### 1.3 Console script

The project defines a single entry point in `[project.scripts]`:

```toml
cql-sdk = "cql_sdk.cli.main:app"
```

### 1.4 Invariants

- The base install **must not** import `pyspark`. CI enforces this by
  installing the built wheel into a clean venv and asserting
  `import pyspark` fails — see
  [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) job
  `lint-type-test`, step *Validate base wheel is Spark-free*.

---

## 2. Module layout

```
src/cql_sdk/
├── __init__.py          # re-exports __version__
├── api.py               # public facade
├── version.py           # __version__ = "0.2.1"
├── abstractions/        # Protocols / ABCs (stable seams)
├── elm/                 # ELM models + (de)serialization
│   ├── models/          # base, expressions, types, library
│   └── serialization/   # loader, json_codec, compatibility
├── runtime/             # context, operators, comparers, quantities, intervals, datetime, definitions
├── compiler/            # planner, expression_builder, type_manager, bindings
│   └── cql_to_elm/      # pure-Python CQL 1.5 → ELM JSON front end (PUBLIC, 0.2.0+)
├── invocation/          # toolkit, invoker, library_registry, cache  (PUBLIC entry point)
├── fhir/                # optional FHIR adapters
├── spark/               # optional Spark adapters (the only place pyspark is imported)
├── packaging/           # library_package, manifest, resource_writer, bundle_writer
└── cli/                 # Typer application + subcommands
```

Data flow for a normal invocation:

```
.elm.json                               .cql
   |                                     |
   |                                     v
   |                  cql_sdk.compiler.cql_to_elm.translate
   |                                     |
   v                                     v
 cql_sdk.elm.serialization.loader.load_library_from_path / _from_string
 → cql_sdk.elm.models.library.Library
 → cql_sdk.invocation.toolkit.InvocationToolkit.invoke
 → cql_sdk.runtime.context.RuntimeContext.evaluate_definition
 → cql_sdk.runtime.operators.evaluate
 → result
```

---

## 3. Public API contract

### 3.1 `cql_sdk.api`

Implemented in [`src/cql_sdk/api.py`](../src/cql_sdk/api.py).

| Function                                                                 | Contract                                                                                                  |
|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| `load_library(path: str \| Path) -> Library`                             | Load an ELM library from a JSON file; raises `FileNotFoundError` if missing.                              |
| `load_library_from_text(text: str) -> Library`                           | Load an ELM library from a JSON string.                                                                   |
| `load_library_from_cql(path: str \| Path) -> Library`                    | Compile a `.cql` source file via `cql_to_elm.compile_file` and load it; raises `CqlError` on bad CQL.    |
| `load_library_from_cql_text(text: str) -> Library`                       | Compile a CQL source string via `cql_to_elm.translate` and load it.                                       |
| `create_context(**overrides) -> RuntimeContext`                          | Build a default `RuntimeContext`; unknown fields raise `TypeError`.                                       |
| `invoke(library, *, definition, parameters=None, context=None) -> Any`   | Evaluate `definition` against `library`; returns the evaluated value or `None` for null-valued semantics. |

### 3.2 `cql_sdk.invocation.toolkit.InvocationToolkit`

Implemented in [`src/cql_sdk/invocation/toolkit.py`](../src/cql_sdk/invocation/toolkit.py).

| Method                                                                                                | Contract                                                                                                                        |
|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| `register(library: Library) -> None`                                                                  | Register a library under both `id` and `id\|version` keys.                                                                      |
| `has(identifier) -> bool`                                                                             | Return whether a library is registered for the identifier.                                                                      |
| `validate(identifier) -> set[str]`                                                                    | Return the set of ELM node types referenced by the library but absent from the operator registry; empty set means executable.   |
| `invoke(*, library_identifier, definition, parameters=None, context=None) -> Any`                    | Evaluate `definition`. Results are cached per `(library_id, definition, hash(parameters))` until `clear_cache` is called.       |
| `clear_cache() -> None`                                                                               | Drop all cached results.                                                                                                        |

### 3.3 `cql_sdk.runtime.context.RuntimeContext`

Implemented in [`src/cql_sdk/runtime/context.py`](../src/cql_sdk/runtime/context.py).

Fields (all publicly settable via `RuntimeContext.default(**overrides)`):

- `library: Library | None`
- `operators: DefaultOperatorRegistry` (the default built-ins are preloaded)
- `parameters: dict[str, Any]`
- `now: datetime` (defaults to `datetime.now(UTC)` at construction time)
- `terminology: TerminologyProvider | None`
- `data_source: DataSource | None`

Methods:

- `with_library(library) -> Self` — attach a library and clear the cache.
- `with_parameters(params) -> Self` — replace parameters and clear the cache.
- `evaluate(node: ElmNode) -> Any` — dispatch a single ELM node.
- `evaluate_definition(name: str) -> Any` — evaluate + cache a named def.

### 3.4 Abstractions (seams)

[`src/cql_sdk/abstractions/`](../src/cql_sdk/abstractions/) defines Protocols:

- `OperatorRegistry` — `register`, `get`, `has`.
- `TypeConverter` — `to_python`, `to_cql`.
- `TerminologyProvider` — `expand`, `in_value_set`; helpers `Code`, `ValueSetRef`.
- `DataSource` — `retrieve(data_type, code_property, codes, date_property, date_range, context)`.
- `PackageWriter` — `write(output_dir, manifest, resources) -> Path`.
- `Invoker` — `invoke(library_identifier, definition, parameters, context) -> Any`.

---

## 4. ELM model and loading

### 4.1 Shape normalization

[`cql_sdk.elm.serialization.compatibility`](../src/cql_sdk/elm/serialization/compatibility.py)
normalizes variant ELM JSON shapes before the loader sees them:

- A top-level `{"library": {...}}` envelope is unwrapped.
- `statements`, `parameters`, `includes` are read from their `def` lists
  regardless of surrounding nesting.

### 4.2 `Library` model

[`cql_sdk.elm.models.library.Library`](../src/cql_sdk/elm/models/library.py) carries:

- `identifier: LibraryIdentifier` (`id`, optional `version`; `str(...)` returns `id` or `id|version`).
- `definitions: dict[str, LibraryDefinition]` keyed by `name`.
- `parameters: dict[str, ElmNode]`.
- `includes: list[LibraryIdentifier]`.
- `value_sets`, `code_systems`: dict of raw JSON defs keyed by `name`.
- `raw`: the original parsed JSON, preserved for pass-through.

`LibraryDefinition` fields: `name`, `expression: ElmNode`, `access_level`
(default `"Public"`), optional `context`.

### 4.3 `ElmNode`

[`cql_sdk.elm.models.base.ElmNode`](../src/cql_sdk/elm/models/base.py) is a
loose wrapper: `type: str` (the ELM discriminator) plus the full payload
dict. This preserves fidelity with the JSON form and lets the runtime
interpret nodes without a full schema port.

---

## 5. Built-in operators

Implemented in
[`cql_sdk.runtime.operators`](../src/cql_sdk/runtime/operators.py). The
`DefaultOperatorRegistry` preloads these:

| ELM type(s)                                                  | Behavior                                                             |
|--------------------------------------------------------------|----------------------------------------------------------------------|
| `Literal`                                                    | Coerce by `valueType` suffix: `Integer → int`, `Decimal → Decimal`, `Boolean → bool`, else string pass-through. |
| `Null`                                                       | Return `None`.                                                       |
| `Add`, `Subtract`, `Multiply`, `Divide`, `TruncatedDivide`   | Binary arithmetic; `None` if any operand is `None`; division guards against zero. |
| `Equal`, `Equivalent`, `NotEqual`                            | Three-valued comparison (returns `None` if either side is `None`).   |
| `Greater`, `GreaterOrEqual`, `Less`, `LessOrEqual`           | Three-valued comparison.                                             |
| `And`, `Or`                                                  | Three-valued boolean logic (short-circuit on `False`/`True`).        |
| `Not`                                                        | Three-valued negation.                                               |
| `If`                                                         | Evaluate `condition`; dispatch to `then` or `else` branch.           |
| `List`, `Tuple`, `Interval`                                  | Construct the corresponding aggregate value.                         |
| `ExpressionRef`                                              | Resolve the named definition via `RuntimeContext.evaluate_definition` (cached). |
| `ParameterRef`                                               | Look up the name in `RuntimeContext.parameters`; missing names return `None`. |

Extending the registry is supported: feature layers (FHIR, Spark, custom)
may call `operators.register(elm_type, fn)` on a shared registry.

The planner [`cql_sdk.compiler.planner.missing_operators`](../src/cql_sdk/compiler/planner.py)
walks a library's expressions and reports every ELM `type` string that
has no registered operator — this is what `InvocationToolkit.validate`
calls.

---

## 5a. CQL → ELM front end (0.2.0+)

[`cql_sdk.compiler.cql_to_elm`](../src/cql_sdk/compiler/cql_to_elm/) is
a pure-Python front end that lets the SDK consume `.cql` source files
without an external Java toolchain.

### 5a.1 Public surface

| Symbol                                  | Contract                                                                  |
|-----------------------------------------|---------------------------------------------------------------------------|
| `translate(text: str) -> dict`          | Tokenize, parse, and emit an ELM JSON document wrapped in `{"library": ...}`. |
| `compile_text(text: str) -> dict`       | Alias for `translate`.                                                    |
| `compile_file(path) -> dict`            | Read a `.cql` file from disk and translate it. Raises `FileNotFoundError` if missing. |
| `CqlError` (and subclasses `CqlLexError`, `CqlParseError`, `CqlTranslationError`) | Carry `line`/`column` location info when available. |

### 5a.2 Supported subset

The accepted grammar is the one implemented in
[`compiler/cql_to_elm/parser.py`](../src/cql_sdk/compiler/cql_to_elm/parser.py):

- Header: `library`, `using`, `include ... called`, `codesystem`,
  `valueset`, `code ... from ... display`, `parameter`, `context`,
  `define`.
- Literals: boolean, integer, decimal, single-quoted strings, `null`,
  `@`-prefixed Date/DateTime, and Quantity (`9.0 'mm[Hg]'`).
- References: unquoted identifiers, quoted identifiers, property
  access (`E.period`), fluent function calls (`E.extension("url")`),
  qualified function calls (`FHIRHelpers.ToConcept(x)`).
- Operators (precedence low→high): `or`, `and`, `not`, equality /
  equivalence (`= != ~`), ordering (`< <= > >=`), interval/membership
  (`in during overlaps before after ends during starts during is null
  is not null`), additive (`+ -`), multiplicative (`* /`), unary
  (`- exists start of end of date from singleton from flatten duration in <p> of`),
  cast (`as Type`).
- Aggregates: `Interval[a, b)`, list literals `{...}`, retrieves
  `[Resource: "ValueSet"]`, query expressions
  `<source> <alias> [where ...] [sort by ...] [return ...]`.

### 5a.3 Out-of-scope (raises `CqlParseError`)

- `let`, `case`, `if/then/else`, `with ... such that`, function
  declarations, multi-source queries (`from A a, B b`), tuple literals,
  full type inference, cross-library expression resolution.

### 5a.4 Output guarantees

- The returned dict has shape `{"library": {...}}` and is directly
  consumable by
  [`elm.serialization.loader.load_library_from_string`](../src/cql_sdk/elm/serialization/loader.py)
  (via `json.dumps`).
- Symbol resolution selects the correct ELM ref kind per identifier:
  parameter names → `ParameterRef`, value-set names → `ValueSetRef`,
  code-system names → `CodeSystemRef`, code names → `CodeRef`, active
  query aliases → `AliasRef`, everything else → `ExpressionRef`.
- `Retrieve` nodes get a `dataType` namespaced under
  `{http://hl7.org/fhir}` and a `codeProperty` defaulted from the
  resource type (`Encounter→type`, `Observation→code`, etc.).
- `Date`/`DateTime` literals split into integer `Literal` operands per
  component, matching the standard ELM shape.

### 5a.5 Non-goals for 0.2.x

The front end is parse-only. Runtime evaluation of the produced ELM
still requires registered operators for every node type the library
references; `InvocationToolkit.validate` reports anything missing.
Adding interpretation for retrieves, queries, and FHIR-specific
operators is reserved for a future release.

---

## 6. FHIR integration (extra `fhir`)

[`cql_sdk.fhir`](../src/cql_sdk/fhir/):

- `context_from_bundle(bundle, **overrides) -> RuntimeContext` — build a
  runtime context whose `data_source` is a `BundleDataSource`.
- `BundleDataSource(bundle)` — minimal `DataSource`: indexes entries by
  `resource.resourceType`; `retrieve(data_type=...)` returns all
  resources of that type.
- `InMemoryTerminology(value_sets)` — tiny `TerminologyProvider` used in
  tests and examples.
- `build_context(bundle, terminology)` — convenience adapter combining
  the two.
- `type_conversion.resource_id` / `resource_type` — light accessors over
  raw resource dicts; the SDK does not bind to a specific FHIR Python
  model library.

---

## 7. Spark integration (extra `spark`)

[`cql_sdk.spark`](../src/cql_sdk/spark/). `pyspark` imports live behind
`TYPE_CHECKING` or inside function scopes so base installs never fail.

- `SparkInvocation(spark, toolkit)`
  - `from_elm_path(path, *, spark) -> SparkInvocation` — load + register
    a library using the core (non-Spark) path, then attach a Spark session.
  - `run(*, definition, library_identifier=None, parameters=None) -> DataFrame`
    — evaluate on the driver, normalize scalar/list results into rows,
    return a DataFrame.
- `make_definition_udf(toolkit, *, library, definition)` — factory
  producing a pure-Python callable suitable for `pyspark.sql.functions.udf`.
  Positional args map to parameters named `arg0`, `arg1`, ….
- `evaluate_over_dataframe(*, df, library, definition, toolkit=None)` —
  evaluate per row (collected). Intended for small / offline datasets;
  production pipelines should prefer UDFs.
- `adapters.dataframe_to_records(df)` — `[Row.asDict(recursive=True)]`.

Spark tests are marked `spark` and only run when the `spark` extra is
installed. CI runs them in a separate gated job.

---

## 8. Packaging primitives

[`cql_sdk.packaging`](../src/cql_sdk/packaging/):

- `PackageManifest(name, version="0.0.0", libraries=[], resources=[], metadata={})`
  with `to_dict()`.
- `LibraryPackage`
  - `LibraryPackage.discover(source_dir, *, name=None)` scans
    `**/*.elm.json` as libraries and all other `**/*.json` as resources,
    producing a manifest with paths relative to `source_dir`.
  - `write(output_dir) -> Path` copies the files under
    `output_dir/<manifest.name>/…` and writes `manifest.json`.
  - `describe()` returns a dict with source path + manifest for tooling.
- `bundle_writer.write_bundle(resources, path)` emits a FHIR
  `Bundle` of type `collection`.
- `resource_writer.write_resource(resource, path)` writes a single
  indented-JSON resource.

---

## 9. CLI

Entry point: `cql-sdk` (Typer app). Implementation in
[`src/cql_sdk/cli/main.py`](../src/cql_sdk/cli/main.py).

| Command                                                                       | Behavior                                                                                                             |
|-------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `cql-sdk --version`                                                           | Print the SDK version and exit.                                                                                      |
| `cql-sdk compile <CQL_FILE> [--output <ELM_JSON>] [--indent N]`              | Compile a CQL source file to ELM JSON; writes to `--output` or stdout (added in 0.2.0).                              |
| `cql-sdk inspect <ELM_FILE>`                                                  | Print identifier, includes, a definitions table (name, access, context, expression type), and parameters.            |
| `cql-sdk validate <ELM_FILE>`                                                 | Exit `0` if all ELM nodes are executable, `1` with a list of missing operator types otherwise.                       |
| `cql-sdk run <ELM_FILE> --definition <NAME> [--bundle <FILE>]`                | Evaluate `<NAME>`; optional `--bundle` attaches a FHIR Bundle `DataSource`; prints a JSON-safe `{definition, result}`. |
| `cql-sdk package <INPUT_DIR> --output <DIR> [--name <NAME>]`                  | Discover and write a `LibraryPackage` to `<DIR>/<name>/` with a `manifest.json`.                                     |

---

## 10. Testing

Test markers defined in [`pyproject.toml`](../pyproject.toml):

- `unit` — fast, isolated (`tests/unit/`).
- `integration` — end-to-end ELM loading / invocation (`tests/integration/`).
- `spark` — requires `pyspark`; skipped automatically when not installed.

Default run (`uv run pytest -m "not spark"`) executes
`unit + integration` and must remain green. As of this version the suite
contains **29 tests** covering:

- Loader: identifier + definitions extraction.
- Invocation: `Sum` returns `42`, `Greeting` returns `"Hello, world!"`,
  and `validate` reports an empty set for the bundled hello-world library.
- Runtime operators: arithmetic, three-valued boolean logic,
  `ParameterRef`.
- End-to-end: `cql_sdk.api.invoke` over an on-disk ELM file.
- **CQL front end (0.2.0+)**: lexer, parser, and translator unit tests
  plus an integration test that compiles three real CMS measure files
  (`CMS122v11`, `CMS165v9`, `ePC02`) and verifies the produced ELM
  loads through the SDK loader with the expected definitions,
  parameters, and value sets.

A `spark` smoke test is provided under `tests/integration/` and is
skipped unless `pyspark` is importable.

Fixtures for the CQL front end live in
[`tests/fixtures/cql/`](../tests/fixtures/cql/): inline source strings
for lexer/parser units plus copies of the three project measure files
under `tests/fixtures/cql/measures/`.

---

## 11. CI

Defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

Job `lint-type-test` (Ubuntu, Python 3.12):

1. Install uv.
2. `uv sync --extra dev --extra test`.
3. `uv run ruff check .`.
4. `uv run mypy`.
5. `uv run pytest -m "not spark" --cov=cql_sdk --cov-report=xml`.
6. `uv build`.
7. Install the built wheel into a clean venv and verify `import cql_sdk`
   and `import cql_sdk.cli.main` succeed while `import pyspark` fails.

Job `spark` (gated — push to `main` or the PR label `run-spark`):

1. Set up JDK 17 (required by PySpark).
2. `uv sync --extra dev --extra test --extra spark`.
3. `uv run pytest -m spark`.

---

## 12. Examples

- [`examples/hello_world/`](../examples/hello_world/) — self-contained
  `HelloWorld.elm.json` plus a Python script that loads and invokes
  `Greeting` and `Sum` through `cql_sdk.api`.
- [`examples/fhir_bundle_execution/`](../examples/fhir_bundle_execution/)
  — attaches a `BundleDataSource` to a runtime context.
- [`examples/spark_demo/`](../examples/spark_demo/) — requires the
  `spark` extra; materializes results as a Spark DataFrame.

---

## 13. Versioning and non-goals

- Version string is centralized in
  [`src/cql_sdk/version.py`](../src/cql_sdk/version.py) and must equal
  the `project.version` in `pyproject.toml`. Both are currently `0.2.1`.
- This release implements a deliberately thin vertical slice of CQL
  semantics; full operator coverage, measure evaluation, terminology
  server integration, and richer FHIR model binding are future work and
  are **out of scope** for 0.2.x unless introduced as new additive
  public surface.
- The `cql_to_elm` front end accepts a documented subset of CQL 1.5 (see
  [`src/cql_sdk/compiler/cql_to_elm/parser.py`](../src/cql_sdk/compiler/cql_to_elm/parser.py)).
  Constructs outside that subset — including `let`, `case`, `with ... such that`,
  function definitions, and cross-library expression resolution — raise
  `CqlParseError` and are out of scope for 0.2.x.

---

## 14. Traceability

| Requirement in this spec                               | Source of truth                                                                 |
|--------------------------------------------------------|---------------------------------------------------------------------------------|
| Package metadata / extras / script                     | [`pyproject.toml`](../pyproject.toml)                                           |
| Public API surface                                     | [`src/cql_sdk/api.py`](../src/cql_sdk/api.py), [`src/cql_sdk/invocation/toolkit.py`](../src/cql_sdk/invocation/toolkit.py), [`src/cql_sdk/compiler/cql_to_elm/`](../src/cql_sdk/compiler/cql_to_elm/) |
| Operator set + semantics                               | [`src/cql_sdk/runtime/operators.py`](../src/cql_sdk/runtime/operators.py)       |
| ELM loading / compatibility                            | [`src/cql_sdk/elm/serialization/`](../src/cql_sdk/elm/serialization/)           |
| CQL → ELM front end                                    | [`src/cql_sdk/compiler/cql_to_elm/`](../src/cql_sdk/compiler/cql_to_elm/)       |
| Runtime context                                        | [`src/cql_sdk/runtime/context.py`](../src/cql_sdk/runtime/context.py)           |
| Abstractions                                           | [`src/cql_sdk/abstractions/`](../src/cql_sdk/abstractions/)                     |
| FHIR adapters                                          | [`src/cql_sdk/fhir/`](../src/cql_sdk/fhir/)                                     |
| Spark adapters                                         | [`src/cql_sdk/spark/`](../src/cql_sdk/spark/)                                   |
| Packaging primitives                                   | [`src/cql_sdk/packaging/`](../src/cql_sdk/packaging/)                           |
| CLI                                                    | [`src/cql_sdk/cli/`](../src/cql_sdk/cli/)                                       |
| CI guarantees                                          | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)                       |
| Governance rules                                       | [`.speckit/constitution.md`](constitution.md)                                   |
