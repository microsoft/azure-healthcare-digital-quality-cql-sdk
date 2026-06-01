"""Execute a CQL library against an in-memory FHIR bundle."""

from __future__ import annotations

from pathlib import Path

from cql_sdk.elm.serialization.loader import load_library_from_path
from cql_sdk.fhir.context import context_from_bundle
from cql_sdk.invocation.toolkit import InvocationToolkit

ELM = Path(__file__).resolve().parents[1] / "hello_world" / "HelloWorld.elm.json"

BUNDLE = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {"resource": {"resourceType": "Patient", "id": "pat-1"}},
        {"resource": {"resourceType": "Observation", "id": "obs-1", "status": "final"}},
    ],
}


def main() -> None:
    library = load_library_from_path(ELM)
    toolkit = InvocationToolkit()
    toolkit.register(library)

    context = context_from_bundle(BUNDLE)
    result = toolkit.invoke(
        library_identifier=library.identifier,
        definition="Greeting",
        context=context,
    )
    print(f"Greeting (with FHIR bundle bound): {result!r}")


if __name__ == "__main__":
    main()
