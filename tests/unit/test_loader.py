import json

import pytest

from cql_sdk.elm.serialization.loader import load_library_from_string


@pytest.mark.unit
def test_loader_extracts_identifier_and_definitions(hello_world_elm_dict):
    lib = load_library_from_string(json.dumps(hello_world_elm_dict))
    assert lib.identifier.id == "HelloWorld"
    assert lib.identifier.version == "1.0.0"
    assert set(lib.definitions) == {"Greeting", "Sum"}
    assert lib.definitions["Greeting"].expression.type == "If"
