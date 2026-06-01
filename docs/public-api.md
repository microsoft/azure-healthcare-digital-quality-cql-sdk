# Public API

Only the following modules are considered **public**. Everything else may
change between minor releases.

## `cql_sdk.api`

Top-level convenience functions.

| Symbol                            | Purpose                                            |
|-----------------------------------|----------------------------------------------------|
| `load_library(path)`              | Load an ELM library from a JSON file.              |
| `load_library_from_text(text)`    | Load an ELM library from a JSON string.            |
| `load_library_from_cql(path)`     | Compile a `.cql` source file and load it.          |
| `load_library_from_cql_text(text)`| Compile a CQL source string and load it.           |
| `create_context(**)`              | Build a default `RuntimeContext`.                  |
| `invoke(library, ...)`            | Evaluate a named definition on a loaded library.   |

## `cql_sdk.compiler.cql_to_elm`

Pure-Python CQL 1.5 (subset) → ELM JSON front end. Added in 0.2.0. Useful
when you need the raw ELM dict (e.g. to inspect, transform, or persist it)
without going through the full library loader.

| Symbol                | Purpose                                                  |
|-----------------------|----------------------------------------------------------|
| `translate(text)`     | Compile a CQL source string to an ELM JSON `dict`.       |
| `compile_text(text)`  | Alias for `translate`.                                   |
| `compile_file(path)`  | Read a `.cql` file and return its ELM JSON `dict`.       |
| `CqlError`            | Base exception (`CqlLexError`, `CqlParseError`, ...).    |

The accepted grammar is documented in
[`compiler/cql_to_elm/parser.py`](../src/cql_sdk/compiler/cql_to_elm/parser.py).
Constructs outside the supported subset (such as `let`, `case`, `with ...
such that`, function declarations, and full type inference) raise
`CqlParseError`.

## `cql_sdk.invocation.toolkit`

Preferred entry point for applications that need more control than `api`.

```python
from cql_sdk.invocation.toolkit import InvocationToolkit

toolkit = InvocationToolkit()
toolkit.register(library)
toolkit.validate(library.identifier)               # operator coverage check
result = toolkit.invoke(
    library_identifier=library.identifier,
    definition="Greeting",
    parameters={"x": 1},
)
```

The toolkit hides:

- library registration / version resolution
- operator registry wiring
- result caching
- ELM serializer compatibility

## `cql_sdk.runtime.context.RuntimeContext`

Exposed so callers can override `parameters`, `now`, `terminology`, and
`data_source`. `RuntimeContext.default(**overrides)` is the supported
construction path.

## `cql_sdk.fhir` (optional extra: `fhir`)

- `context_from_bundle(bundle)` — build a RuntimeContext with a
  bundle-backed `DataSource`.
- `BundleDataSource`, `InMemoryTerminology` — plug-in-ready implementations.

## `cql_sdk.spark` (optional extra: `spark`)

- `SparkInvocation` — DataFrame-producing facade mirroring
  `InvocationToolkit`.
- `make_definition_udf` — wrap a CQL definition as a Spark UDF factory.

## `cql_sdk.packaging`

- `LibraryPackage.discover(src)` / `.write(out)`
- `PackageManifest`
- `bundle_writer.write_bundle` / `resource_writer.write_resource`

## `cql_sdk.cli`

Exposed as the `cql-sdk` console script. Not intended to be imported
programmatically.

| Command                                            | Purpose                                       |
|----------------------------------------------------|-----------------------------------------------|
| `cql-sdk compile <CQL_FILE> [--output ELM.json]`   | Compile CQL source to ELM JSON.               |
| `cql-sdk inspect <ELM_FILE>`                       | Print a human-readable summary.               |
| `cql-sdk validate <ELM_FILE>`                      | Check operator coverage.                      |
| `cql-sdk run <ELM_FILE> --definition <name>`       | Evaluate a definition.                        |
| `cql-sdk package <INPUT_DIR> --output <OUT>`       | Package an ELM/resource directory.            |

## Internal modules

`cql_sdk.compiler.planner`, `cql_sdk.compiler.bindings`,
`cql_sdk.runtime.operators`, and everything not listed above are
**internal**. They are documented in the source but may change without
notice. (Note: `cql_sdk.compiler.cql_to_elm` *is* public — see above.)
