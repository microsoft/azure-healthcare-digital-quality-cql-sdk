import json

import pytest

from cql_sdk.elm.serialization.loader import load_library_from_string
from cql_sdk.invocation.toolkit import InvocationToolkit


@pytest.mark.unit
def test_invoke_sum(hello_world_elm_dict):
    lib = load_library_from_string(json.dumps(hello_world_elm_dict))
    tk = InvocationToolkit()
    tk.register(lib)
    assert tk.invoke(library_identifier=lib.identifier, definition="Sum") == 42


@pytest.mark.unit
def test_invoke_greeting(hello_world_elm_dict):
    lib = load_library_from_string(json.dumps(hello_world_elm_dict))
    tk = InvocationToolkit()
    tk.register(lib)
    assert tk.invoke(library_identifier=lib.identifier, definition="Greeting") == "Hello, world!"


@pytest.mark.unit
def test_validate_all_operators_supported(hello_world_elm_dict):
    lib = load_library_from_string(json.dumps(hello_world_elm_dict))
    tk = InvocationToolkit()
    tk.register(lib)
    assert tk.validate(lib.identifier) == set()
