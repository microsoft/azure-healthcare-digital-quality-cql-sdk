# Architecture

`cql-sdk` is organized into layered, deliberately small packages. Each layer
has a single responsibility and talks to the layers above and below through
narrow interfaces defined in `cql_sdk.abstractions`.

```
                  +-----------------------------+
        user  →   |  cql_sdk.api                |   (public facade)
                  +-------------+---------------+
                                |
              +-----------------+-----------------+
              |                                   |
+-------------v---------------+      +------------v--------------+
|  cql_sdk.compiler.cql_to_elm |     |  cql_sdk.invocation       |
|  (lexer + parser +           |     |  registry / invoker /     |
|   AST + ELM emitter)         |     |  cache / toolkit          |
+-------------+----------------+     +------------+--------------+
              | ELM JSON                          |
              v                                   |
   +----------+-------------+         +-----------v----------+
   |  cql_sdk.elm           |←--------|  cql_sdk.compiler    |
   |  models + loader       |         |  planner + bindings  |
   +----------+-------------+         +-----------+----------+
              |                                   |
              v                                   v
                       +----------------+
                       | cql_sdk.runtime|
                       | context, ops,  |
                       | comparers      |
                       +----------------+
```

## Layers

1. **`abstractions`** — Protocols and ABCs: `OperatorRegistry`,
   `TerminologyProvider`, `DataSource`, `TypeConverter`, `PackageWriter`,
   `Invoker`. These define the stable seams for the SDK.
2. **`elm`** — Models + serialization. The loader normalizes variant ELM
   shapes before they reach the runtime.
3. **`runtime`** — `RuntimeContext`, operator registry, comparers,
   quantities, intervals, datetime types. Pure Python, no FHIR or Spark.
4. **`compiler`** — Two sub-packages:
   - **`compiler.cql_to_elm`** — Pure-Python CQL 1.5 → ELM JSON front end
     (lexer, recursive-descent parser, AST, translator). Added in 0.2.0.
     Lets consumers go from `.cql` text directly to a loadable Library
     without any Java toolchain.
   - The compiler root (`planner`, `expression_builder`, `type_manager`,
     `bindings`) interprets ELM directly. Designed so a future version
     can pre-compile expressions without breaking consumers.
5. **`invocation`** — `InvocationToolkit`, `LibraryRegistry`, `ResultCache`,
   `Invoker`. The preferred public entry point.
6. **`fhir`** — Optional. Bundle-backed data source, terminology shims,
   context adapters.
7. **`spark`** — Optional. Spark-session facade, DataFrame adapters, UDF
   factories. `pyspark` is only imported inside this package.
8. **`packaging`** — Library package discovery, manifests, resource/bundle
   writers. Produces artifacts consumable by downstream deployment.
9. **`cli`** — Typer application: `compile`, `inspect`, `validate`, `run`,
   `package`.

## Data flow

Two equivalent entry paths converge at the loaded `Library`:

- `.cql` source → `compiler.cql_to_elm.translate` → ELM JSON →
  `elm.serialization.loader` → `elm.models.Library`.
- `.elm.json` artifact → `elm.serialization.loader` → `elm.models.Library`.

From there: `Library` → `invocation.toolkit.InvocationToolkit`
→ `runtime.context.RuntimeContext` → `runtime.operators.evaluate` → result.

## Boundaries

- `runtime` never imports `fhir` or `spark`.
- `spark` never leaks into the base install; importing `cql_sdk.spark`
  fails fast if `pyspark` is missing.
- FHIR model libraries are pluggable via adapters in `cql_sdk.fhir` — the
  base SDK never hard-wires a specific FHIR Python model package.
- `compiler.cql_to_elm` is parse-only: it produces ELM JSON but does not
  attempt to evaluate it. Anything runtime-related still flows through
  `invocation` and `runtime`.
