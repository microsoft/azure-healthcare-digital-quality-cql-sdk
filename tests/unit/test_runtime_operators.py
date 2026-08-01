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


def _dt(value):
    return {
        "type": "Literal",
        "valueType": "{urn:hl7-org:elm-types:r1}DateTime",
        "value": value,
    }


@pytest.mark.unit
def test_now_is_naive_and_today_is_date():
    from datetime import date, datetime

    ctx = RuntimeContext.default()
    now = ctx.evaluate(ElmNode.from_json({"type": "Now"}))
    assert isinstance(now, datetime) and now.tzinfo is None
    today = ctx.evaluate(ElmNode.from_json({"type": "Today"}))
    assert isinstance(today, date)


@pytest.mark.unit
def test_duration_between_counts_completed_periods():
    ctx = RuntimeContext.default()

    def dur(precision, a, b):
        return ctx.evaluate(
            ElmNode.from_json(
                {"type": "DurationBetween", "precision": precision, "operand": [_dt(a), _dt(b)]}
            )
        )

    assert dur("year", "2020-06-15T00:00:00", "2026-06-14T00:00:00") == 5
    assert dur("month", "2026-01-15T00:00:00", "2026-03-14T00:00:00") == 1
    assert dur("day", "2026-01-01T00:00:00", "2026-01-29T00:00:00") == 28
    assert dur("week", "2026-01-01T00:00:00", "2026-01-29T00:00:00") == 4
    # Reversed operands truncate toward zero (symmetric magnitude).
    assert dur("week", "2026-01-29T00:00:00", "2026-01-01T00:00:00") == -4


@pytest.mark.unit
def test_difference_between_counts_boundaries():
    ctx = RuntimeContext.default()

    def diff(precision, a, b):
        return ctx.evaluate(
            ElmNode.from_json(
                {"type": "DifferenceBetween", "precision": precision, "operand": [_dt(a), _dt(b)]}
            )
        )

    # One calendar-year boundary crossed even though under a day apart.
    assert diff("year", "2020-12-31T00:00:00", "2021-01-01T00:00:00") == 1
    assert diff("month", "2026-01-31T00:00:00", "2026-02-01T00:00:00") == 1
