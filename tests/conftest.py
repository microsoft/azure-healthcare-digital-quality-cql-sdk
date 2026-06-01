import json
from pathlib import Path

import pytest

from tests.fixtures.elm.hello_world import HELLO_WORLD_ELM


@pytest.fixture
def hello_world_elm_dict() -> dict:
    return HELLO_WORLD_ELM


@pytest.fixture
def hello_world_elm_path(tmp_path: Path) -> Path:
    p = tmp_path / "HelloWorld.elm.json"
    p.write_text(json.dumps(HELLO_WORLD_ELM), encoding="utf-8")
    return p
