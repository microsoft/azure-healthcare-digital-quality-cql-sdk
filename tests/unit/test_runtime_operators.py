import pytest

from cql_sdk.elm.models.base import ElmNode
from cql_sdk.runtime.context import RuntimeContext


def _lit(value, vtype="Integer"):
    return {"type": "Literal", "valueType": f"{{...}}{vtype}", "value": str(value)}


@pytest.mark.unit
def test_add_subtract_multiply_divide():
    ctx = RuntimeContext.default()
    assert ctx.evaluate(ElmNode.from_json({"type": "Add", "operand": [_lit(2), _lit(3)]})) == 5
    assert ctx.evaluate(ElmNode.from_json({"type": "Subtract", "operand": [_lit(5), _lit(3)]})) == 2
    assert ctx.evaluate(ElmNode.from_json({"type": "Multiply", "operand": [_lit(4), _lit(3)]})) == 12
    assert ctx.evaluate(ElmNode.from_json({"type": "Divide", "operand": [_lit(10), _lit(2)]})) == 5


@pytest.mark.unit
def test_boolean_three_valued():
    ctx = RuntimeContext.default()
    tree = {
        "type": "And",
        "operand": [
            {"type": "Literal", "valueType": "Boolean", "value": "true"},
            {"type": "Null"},
        ],
    }
    assert ctx.evaluate(ElmNode.from_json(tree)) is None


@pytest.mark.unit
def test_parameter_ref():
    ctx = RuntimeContext.default().with_parameters({"x": 99})
    assert ctx.evaluate(ElmNode.from_json({"type": "ParameterRef", "name": "x"})) == 99
