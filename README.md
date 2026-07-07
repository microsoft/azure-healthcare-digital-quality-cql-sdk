# cql-sdk

> **Install from PyPI:** **`pip install ms-cql-sdk`**
>
> Published at <https://pypi.org/project/ms-cql-sdk/>. The Python import name remains `cql_sdk`.

A modular Python SDK for working with **Clinical Quality Language (CQL)** and
its compiled form **ELM** (Expression Logical Model). Inspired by the layering
of the Firely C# CQL SDK, but designed idiomatically for Python and for modern
data platforms (standalone, containers, PySpark, Microsoft Fabric).

> Status: early scaffold. The architecture, public API surface and extension
> points are deliberately sketched so they can grow toward a fuller CQL
> engine without breaking consumers.

## Disclaimer

This SDK is provided as-is under the MIT license. It is a general
purpose CQL/ELM execution toolkit and does not include or grant any rights
to third-party measure specifications, value sets, or code systems.

If you use this SDK to compute **HEDIS&reg;** measures in production, you
are responsible for obtaining the appropriate license from **NCQA**.
HEDIS is a registered trademark of the National Committee for Quality
Assurance (NCQA). See <https://www.ncqa.org/hedis/measures/> for measure
licensing terms.

The same applies to other proprietary measure stewards (for example, CMS
eCQM artifacts may have their own usage terms, and any LOINC, SNOMED CT,
RxNorm, ICD, or CPT content carries its own licensing).

## What's new in 0.4.3

- License changed from Apache-2.0 to MIT.
- Added Origins and Attribution, Acknowledgements, and Relationship to Firely CQL SDK sections to README.

## What's new in 0.4.2

- Project URL metadata now points at the canonical
  `github.com/microsoft/azure-healthcare-digital-quality-cql-sdk`
  repository.
- Added **Disclaimer** section covering HEDIS&reg; / NCQA licensing
  responsibilities for production use, and a note on third-party
  terminology content (LOINC, SNOMED CT, RxNorm, ICD, CPT).

## What's new in 0.4.1

- README: surface the 0.3.0 and 0.4.0 release notes on the PyPI project
  page (no code changes).

## What's new in 0.4.0

- **Spark adapter fix**: `SparkInvocation.run` now uses the library
  registered via `from_elm_path` instead of the first entry in the toolkit
  registry, which was the auto-registered synthetic `FHIRHelpers`. Fixes
  `KeyError: "Definition '<name>' not found in library 'FHIRHelpers|4.0.1'."`.
- `SparkInvocation` accepts an explicit `default_library_identifier` for
  callers constructing the toolkit directly.

## What's new in 0.3.0

- Invocation toolkit auto-registers a synthetic `FHIRHelpers` library so
  measures that `include FHIRHelpers` resolve without an extra step.
- Public API consolidation around `InvocationToolkit` (`register`, `has`,
  `validate`, `invoke`) as the preferred entry point.
- Library registry de-duplicates `id` and `id|version` keys during
  iteration.

## What's new in 0.2.1

- Internal: ruff and mypy `--strict` are now both clean (parser/translator
  refactors broke long lines into helpers, no behavior change). Aligns the
  package with the CI gates so downstream forks pass on a clean checkout.

## What's new in 0.2.0

- **Pure-Python CQL → ELM front end** under
  [`cql_sdk.compiler.cql_to_elm`](src/cql_sdk/compiler/cql_to_elm/) — no Java
  required. Covers the CQL 1.5 subset used by typical CMS eCQM measures:
  library/using/include/codesystem/valueset/code/parameter/context/define,
  retrieves and queries with where/sort/return, all standard arithmetic and
  comparison operators, interval/list literals, casts, and fluent function
  calls (`X.extension("...")`).
- New public API: `cql_sdk.api.load_library_from_cql` and
  `load_library_from_cql_text`.
- New CLI command: `cql-sdk compile <CQL_FILE> [--output ELM.json]`.

## Why this SDK

- Pure-Python core for ELM loading, runtime context, operators, invocation.
- Optional FHIR integration (retrieval, type conversion, terminology).
- Optional Spark / Microsoft Fabric integration (the *same* core package
  runs unchanged in both environments).
- A Typer-based CLI for inspecting, validating, packaging and running ELM.
- Designed around *pre-generated ELM artifacts* as a first-class workflow —
  no Java/CQL-to-ELM toolchain is required for normal execution.

## Package layering

```
 cql_sdk
 ├── abstractions/   # Protocols / ABCs for operators, terminology, data, packaging
 ├── elm/            # ELM model + (de)serialization
 ├── runtime/        # RuntimeContext, operators, comparers, intervals, datetime
 ├── compiler/       # Expression planner, bindings, type manager
 ├── invocation/     # High-level toolkit / invoker / library registry (PUBLIC API)
 ├── fhir/           # Optional FHIR adapters
 ├── spark/          # Optional Spark / Fabric adapters
 ├── packaging/      # Library + resource packaging primitives
 ├── cli/            # Typer CLI (`cql-sdk`)
 └── api.py          # Top-level convenience facade (PUBLIC API)
```

The **invocation toolkit** and [`cql_sdk.api`](src/cql_sdk/api.py) are the
preferred entry points. Internal modules (`compiler`, low-level runtime) are
available but not the recommended consumption path.

## Quick start

### Install (base)

```bash
uv sync
```

### Install with optional extras

```bash
uv sync --extra fhir
uv sync --extra spark        # pulls pyspark; not required for base install
uv sync --extra dev --extra test
```

### Run the local hello-world example

```bash
uv run python examples/hello_world/run.py
```

### Load ELM and invoke a definition (Python)

```python
from cql_sdk.api import load_library, invoke

library = load_library("examples/hello_world/HelloWorld.elm.json")
result = invoke(library, definition="Greeting")
print(result)
```

### Compile a CQL source file (no Java required)

```python
from cql_sdk.api import load_library_from_cql

library = load_library_from_cql("path/to/Measure.cql")
print(library.identifier)            # CMS122|11
print(list(library.definitions))     # ['Initial Population', 'Numerator', ...]
```

Or get the raw ELM JSON via the lower-level entry point:

```python
from cql_sdk.compiler.cql_to_elm import compile_file
elm = compile_file("path/to/Measure.cql")
```

### Use the CLI

```bash
uv run cql-sdk compile path/to/Measure.cql --output dist/Measure.elm.json
uv run cql-sdk inspect examples/hello_world/HelloWorld.elm.json
uv run cql-sdk validate examples/hello_world/HelloWorld.elm.json
uv run cql-sdk run examples/hello_world/HelloWorld.elm.json --definition Greeting
uv run cql-sdk package examples/hello_world --output dist/packages
```

### Spark / Fabric usage

Spark support is *opt-in*:

```bash
uv sync --extra spark
```

```python
from pyspark.sql import SparkSession
from cql_sdk.spark import SparkInvocation

spark = SparkSession.builder.getOrCreate()
invocation = SparkInvocation.from_elm_path(
    "examples/hello_world/HelloWorld.elm.json", spark=spark
)
df = invocation.run(definition="Greeting")
df.show()
```

Core modules never import `pyspark` — importing `cql_sdk.spark` is the only
place Spark is required.

## Development

```bash
uv sync --extra dev --extra test
uv run ruff check .
uv run mypy
uv run pytest -m "not spark"
uv run pytest -m spark            # requires `--extra spark`
```

See [docs/development.md](docs/development.md) for more.

## Documentation

- [Architecture](docs/architecture.md)
- [Public API](docs/public-api.md)
- [Packaging](docs/packaging.md)
- [Development](docs/development.md)

## License

MIT. See [LICENSE](LICENSE).

This license covers the SDK source code only. It does **not** grant rights
to HEDIS&reg; measure specifications (license from NCQA required for
production use, see the [Disclaimer](#disclaimer) section), nor to any
third-party terminology content (LOINC, SNOMED CT, RxNorm, ICD, CPT, etc.).

## Origins and Attribution

This project was inspired by and derived from concepts demonstrated in the Firely and NCQA CQL SDK project:

- <https://github.com/FirelyTeam/firely-cql-sdk>

The Firely CQL SDK is NCQA's and Firely's official SDK for working with Clinical Quality Language (CQL) on the .NET platform.

The Microsoft Azure Healthcare Digital Quality CQL SDK extends these concepts to support additional healthcare analytics scenarios, including cloud-native execution patterns, Python interoperability, Spark/Fabric integration, and Azure-based deployment models.

We are grateful to Firely and NCQA for their contributions to the CQL ecosystem and for advancing interoperable clinical quality measurement technologies.

The original Firely project and its contributors retain ownership of their respective intellectual property and code contributions. Please refer to the upstream repository for additional details and licensing information.

## Relationship to Firely CQL SDK

This project is not a drop-in replacement for the Firely CQL SDK.

While portions of the architecture, compiler design concepts, and CQL execution patterns were informed by the Firely implementation, this SDK introduces additional capabilities focused on analytics, distributed execution, cloud-native deployment, and modern healthcare data platform integration.

## Acknowledgements

Special thanks to:

- Firely
- NCQA
- HL7 Clinical Quality Language (CQL) Community
- FHIR Community Contributors

for advancing standards-based clinical quality measurement and interoperability.
