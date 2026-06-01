import pytest

from cql_sdk.api import invoke, load_library


@pytest.mark.integration
def test_end_to_end_from_file(hello_world_elm_path):
    lib = load_library(hello_world_elm_path)
    assert invoke(lib, definition="Greeting") == "Hello, world!"
    assert invoke(lib, definition="Sum") == 42
