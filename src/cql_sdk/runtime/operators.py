"""Core operator implementations for the built-in runtime.

The default registry covers the operators needed to evaluate real-world
eCQM measures end-to-end (CMS165v9, CMS122v11, ePC-02 and similar). It is
split into thematic groups for readability:

* literals + null
* arithmetic, comparison, boolean, control flow
* aggregates: List, Tuple, Interval
* references: ExpressionRef, ParameterRef, AliasRef, QueryLetRef,
  CodeRef, CodeSystemRef, ValueSetRef, FunctionRef
* FHIR-aware navigation: Property (with choice-type expansion), As, IsNull
* Lists / collections: Exists, SingletonFrom, First, Last, Count, Length,
  Flatten, Coalesce
* Quantity literal + Quantity-aware comparison (delegated to comparers)
* Date/Time: Date, DateTime, DateFrom, CalculateAge, CalculateAgeAt
* Intervals: Start, End, Overlaps, IncludedIn, Includes, Before, After, In
* Retrieve / Query (with alias scopes, where, sort, return, let)
* Case, Let

The registry is swappable: FHIR or Spark layers can register additional /
override operators without touching this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Any

from dateutil.relativedelta import relativedelta  # type: ignore[import-untyped]

from cql_sdk.abstractions.terminology import Code, ValueSetRef
from cql_sdk.elm.models.base import ElmNode
from cql_sdk.runtime import comparers
from cql_sdk.runtime.intervals import Interval
from cql_sdk.runtime.quantities import Quantity

if TYPE_CHECKING:
    from cql_sdk.runtime.context import RuntimeContext


OperatorFn = Callable[["RuntimeContext", ElmNode], Any]


class DefaultOperatorRegistry:
    """In-memory :class:`OperatorRegistry` with builtins pre-loaded."""

    def __init__(self) -> None:
        self._ops: dict[str, OperatorFn] = {}
        register_builtins(self)

    def register(self, elm_type: str, fn: OperatorFn) -> None:
        self._ops[elm_type] = fn

    def get(self, elm_type: str) -> OperatorFn:
        try:
            return self._ops[elm_type]
        except KeyError as exc:
            raise KeyError(f"No operator registered for ELM type '{elm_type}'.") from exc

    def has(self, elm_type: str) -> bool:
        return elm_type in self._ops


# --- ELM node evaluation --------------------------------------------------


def evaluate(ctx: RuntimeContext, node: ElmNode) -> Any:
    """Dispatch ``node`` to its registered operator implementation."""
    if not node.type:
        return None
    return ctx.operators.get(node.type)(ctx, node)


def _eval_child(ctx: RuntimeContext, raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [_eval_child(ctx, item) for item in raw]
    if isinstance(raw, dict):
        if "type" in raw:
            return evaluate(ctx, ElmNode.from_json(raw))
        return raw
    return raw


def _operands(ctx: RuntimeContext, node: ElmNode) -> list[Any]:
    operand = node.get("operand")
    if operand is None:
        return []
    if isinstance(operand, list):
        return [_eval_child(ctx, o) for o in operand]
    return [_eval_child(ctx, operand)]


# --- literals + null ------------------------------------------------------


def _op_literal(_ctx: RuntimeContext, node: ElmNode) -> Any:
    value = node.get("value")
    value_type = str(node.get("valueType") or "")
    if value is None:
        return None
    if value_type.endswith("Integer"):
        return int(value)
    if value_type.endswith("Decimal"):
        return Decimal(str(value))
    if value_type.endswith("Boolean"):
        return str(value).lower() == "true"
    if value_type.endswith("DateTime") or value_type.endswith("Date"):
        return _parse_dt(value)
    return value


def _op_null(_ctx: RuntimeContext, _node: ElmNode) -> None:
    return None


# --- arithmetic -----------------------------------------------------------


def _op_add(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    if a is None or b is None:
        return None
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return Quantity(value=a.value + b.value, unit=a.unit)
    if isinstance(a, (datetime, date)) and isinstance(b, Quantity):
        return _shift_date(a, b, +1)
    if isinstance(a, Quantity) and isinstance(b, (datetime, date)):
        return _shift_date(b, a, +1)
    return a + b


def _op_sub(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    if a is None or b is None:
        return None
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return Quantity(value=a.value - b.value, unit=a.unit)
    if isinstance(a, (datetime, date)) and isinstance(b, Quantity):
        return _shift_date(a, b, -1)
    return a - b


def _op_mul(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    return None if a is None or b is None else a * b


def _op_div(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    if a is None or b is None or b == 0:
        return None
    return a / b


def _op_negate(ctx: RuntimeContext, node: ElmNode) -> Any:
    val = _operands(ctx, node)
    v = val[0] if val else None
    return None if v is None else -v


# --- comparison -----------------------------------------------------------


def _op_equal(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    return comparers.equal(a, b)


def _op_not_equal(ctx: RuntimeContext, node: ElmNode) -> Any:
    eq = _op_equal(ctx, node)
    return None if eq is None else not eq


def _op_equivalent(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    return comparers.equivalent(a, b)


def _op_greater(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    return comparers.greater(a, b)


def _op_less(ctx: RuntimeContext, node: ElmNode) -> Any:
    a, b = _operands(ctx, node)
    return comparers.less(a, b)


def _op_greater_or_equal(ctx: RuntimeContext, node: ElmNode) -> Any:
    return _combine_or(_op_greater(ctx, node), _op_equal(ctx, node))


def _op_less_or_equal(ctx: RuntimeContext, node: ElmNode) -> Any:
    return _combine_or(_op_less(ctx, node), _op_equal(ctx, node))


# --- boolean / control flow ----------------------------------------------


def _op_and(ctx: RuntimeContext, node: ElmNode) -> Any:
    values = _operands(ctx, node)
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return all(bool(v) for v in values)


def _op_or(ctx: RuntimeContext, node: ElmNode) -> Any:
    values = _operands(ctx, node)
    if any(v is True for v in values):
        return True
    if any(v is None for v in values):
        return None
    return any(bool(v) for v in values)


def _op_xor(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    values = _operands(ctx, node)
    if any(v is None for v in values):
        return None
    return bool(values[0]) ^ bool(values[1])


def _op_not(ctx: RuntimeContext, node: ElmNode) -> Any:
    values = _operands(ctx, node)
    v = values[0] if values else None
    return None if v is None else not v


def _op_if(ctx: RuntimeContext, node: ElmNode) -> Any:
    condition = _eval_child(ctx, node.get("condition"))
    branch = "then" if condition else "else"
    return _eval_child(ctx, node.get(branch))


def _op_case(ctx: RuntimeContext, node: ElmNode) -> Any:
    items = node.get("caseItem") or []
    scrutinee_expr = node.get("comparand")
    has_scrutinee = scrutinee_expr is not None
    scrutinee = _eval_child(ctx, scrutinee_expr) if has_scrutinee else None
    for item in items:
        if not isinstance(item, dict):
            continue
        when_val = _eval_child(ctx, item.get("when"))
        matched = (when_val == scrutinee) if has_scrutinee else (when_val is True)
        if matched:
            return _eval_child(ctx, item.get("then"))
    return _eval_child(ctx, node.get("else"))


# --- aggregates -----------------------------------------------------------


def _op_list(ctx: RuntimeContext, node: ElmNode) -> list[Any]:
    elements = node.get("element") or []
    return [_eval_child(ctx, e) for e in elements]


def _op_to_list(ctx: RuntimeContext, node: ElmNode) -> list[Any]:
    value = _eval_child(ctx, node.get("operand"))
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _op_tuple(ctx: RuntimeContext, node: ElmNode) -> dict[str, Any]:
    elements = node.get("element") or []
    out: dict[str, Any] = {}
    for e in elements:
        if isinstance(e, dict) and "name" in e:
            out[e["name"]] = _eval_child(ctx, e.get("value"))
    return out


def _op_interval(ctx: RuntimeContext, node: ElmNode) -> Interval:
    return Interval(
        low=_eval_child(ctx, node.get("low")),
        high=_eval_child(ctx, node.get("high")),
        low_closed=bool(node.get("lowClosed", True)),
        high_closed=bool(node.get("highClosed", True)),
    )


# --- list operators -------------------------------------------------------


def _op_exists(ctx: RuntimeContext, node: ElmNode) -> bool:
    val = _eval_child(ctx, node.get("operand"))
    if val is None:
        return False
    if isinstance(val, list):
        return any(item is not None for item in val)
    return True


def _op_singleton_from(ctx: RuntimeContext, node: ElmNode) -> Any:
    val = _eval_child(ctx, node.get("operand"))
    if val is None:
        return None
    if not isinstance(val, list):
        return val
    items = [v for v in val if v is not None]
    if not items:
        return None
    if len(items) > 1:
        raise ValueError("singleton from: source list has more than one element")
    return items[0]


def _list_source(ctx: RuntimeContext, node: ElmNode) -> Any:
    raw = node.get("source")
    if raw is None:
        raw = node.get("operand")
    return _eval_child(ctx, raw)


def _op_last(ctx: RuntimeContext, node: ElmNode) -> Any:
    src = _list_source(ctx, node)
    if not isinstance(src, list) or not src:
        return None
    return src[-1]


def _op_first(ctx: RuntimeContext, node: ElmNode) -> Any:
    src = _list_source(ctx, node)
    if not isinstance(src, list) or not src:
        return None
    return src[0]


def _op_count(ctx: RuntimeContext, node: ElmNode) -> int:
    src = _list_source(ctx, node)
    if not isinstance(src, list):
        return 0
    return sum(1 for v in src if v is not None)


def _op_length(ctx: RuntimeContext, node: ElmNode) -> int:
    src = _list_source(ctx, node)
    if src is None:
        return 0
    if isinstance(src, (list, str)):
        return len(src)
    return 0


def _op_flatten(ctx: RuntimeContext, node: ElmNode) -> Any:
    val = _eval_child(ctx, node.get("operand"))
    if not isinstance(val, list):
        return val
    out: list[Any] = []
    for item in val:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


def _op_coalesce(ctx: RuntimeContext, node: ElmNode) -> Any:
    operands = node.get("operand") or []
    if not isinstance(operands, list):
        operands = [operands]
    for op in operands:
        val = _eval_child(ctx, op)
        if val is None:
            continue
        if isinstance(val, list):
            for item in val:
                if item is not None:
                    return item
            continue
        return val
    return None


# --- quantity literal -----------------------------------------------------


def _op_quantity(_ctx: RuntimeContext, node: ElmNode) -> Quantity | None:
    value = node.get("value")
    unit = str(node.get("unit") or "1")
    if value is None:
        return None
    return Quantity(value=Decimal(str(value)), unit=unit)


# --- date / time ----------------------------------------------------------


def _op_datetime(ctx: RuntimeContext, node: ElmNode) -> datetime | None:
    year = _eval_child(ctx, node.get("year"))
    if year is None:
        return None
    month = _eval_child(ctx, node.get("month")) or 1
    day = _eval_child(ctx, node.get("day")) or 1
    hour = _eval_child(ctx, node.get("hour")) or 0
    minute = _eval_child(ctx, node.get("minute")) or 0
    second = _eval_child(ctx, node.get("second")) or 0
    return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))


def _op_date(ctx: RuntimeContext, node: ElmNode) -> date | None:
    year = _eval_child(ctx, node.get("year"))
    if year is None:
        return None
    month = _eval_child(ctx, node.get("month")) or 1
    day = _eval_child(ctx, node.get("day")) or 1
    return date(int(year), int(month), int(day))


def _op_date_from(ctx: RuntimeContext, node: ElmNode) -> Any:
    val = _eval_child(ctx, node.get("operand"))
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return _parse_dt(val)
    return None


def _op_calculate_age_at(ctx: RuntimeContext, node: ElmNode) -> int | None:
    operands = _operands(ctx, node)
    # CQL's ``AgeInYearsAt(asof)`` translates to a single-operand
    # CalculateAgeAt where the birthDate is implicit from the Patient
    # context.
    if len(operands) == 1:
        birth = _patient_birth_date(ctx)
        asof = operands[0]
    elif len(operands) >= 2:
        birth = operands[0]
        asof = operands[1]
    else:
        return None
    if birth is None or asof is None:
        return None
    precision = str(node.get("precision") or "Year").lower()
    return _age_in(birth, asof, precision)


def _op_calculate_age(ctx: RuntimeContext, node: ElmNode) -> int | None:
    operands = _operands(ctx, node)
    if not operands or operands[0] is None:
        return None
    precision = str(node.get("precision") or "Year").lower()
    return _age_in(operands[0], ctx.now, precision)


def _patient_birth_date(ctx: RuntimeContext) -> Any:
    subject = getattr(ctx, "subject", None)
    if not isinstance(subject, dict):
        return None
    bd = subject.get("birthDate")
    if isinstance(bd, str):
        return _parse_dt(bd)
    return bd


# --- intervals ------------------------------------------------------------


def _op_start(ctx: RuntimeContext, node: ElmNode) -> Any:
    operands = _operands(ctx, node)
    val = _coerce_interval(operands[0] if operands else None)
    if isinstance(val, Interval):
        return val.low
    return None


def _op_end(ctx: RuntimeContext, node: ElmNode) -> Any:
    operands = _operands(ctx, node)
    val = _coerce_interval(operands[0] if operands else None)
    if isinstance(val, Interval):
        return val.high
    return None


def _op_overlaps(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if not isinstance(a, Interval) or not isinstance(b, Interval):
        return None
    try:
        # null bounds = unbounded (per CQL spec). Unbounded sides always overlap.
        if a.high is not None and b.low is not None and a.high < b.low:
            return False
        return not (b.high is not None and a.low is not None and b.high < a.low)
    except TypeError:
        return None


def _op_included_in(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if a is None or b is None:
        return None
    if isinstance(b, Interval):
        if isinstance(a, Interval):
            try:
                # null bounds on b = unbounded outer interval, always contains.
                low_ok = b.low is None or (a.low is not None and b.low <= a.low)
                high_ok = b.high is None or (a.high is not None and a.high <= b.high)
                return low_ok and high_ok
            except TypeError:
                return None
        try:
            return b.contains(a)
        except TypeError:
            return None
    if isinstance(b, list):
        return a in b
    return None


def _op_includes(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if a is None or b is None:
        return None
    if isinstance(a, Interval) and isinstance(b, Interval):
        if a.low is None or a.high is None or b.low is None or b.high is None:
            return None
        try:
            return bool(a.low <= b.low and b.high <= a.high)
        except TypeError:
            return None
    if isinstance(a, Interval):
        try:
            return a.contains(b)
        except TypeError:
            return None
    if isinstance(a, list):
        return b in a
    return None


def _op_before(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if a is None or b is None:
        return None
    a_end = a.high if isinstance(a, Interval) else a
    b_start = b.low if isinstance(b, Interval) else b
    if a_end is None or b_start is None:
        return None
    try:
        return bool(a_end < b_start)
    except TypeError:
        return None


def _op_after(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if a is None or b is None:
        return None
    a_start = a.low if isinstance(a, Interval) else a
    b_end = b.high if isinstance(b, Interval) else b
    if a_start is None or b_end is None:
        return None
    try:
        return bool(a_start > b_end)
    except TypeError:
        return None


def _op_ends(ctx: RuntimeContext, node: ElmNode) -> Any:
    """``ends X`` returns the end of an interval (``X.high``)."""
    val = _eval_child(ctx, node.get("operand"))
    val = _coerce_interval(val)
    return val.high if isinstance(val, Interval) else None


def _op_starts(ctx: RuntimeContext, node: ElmNode) -> Any:
    """``starts X`` returns the start of an interval (``X.low``)."""
    val = _eval_child(ctx, node.get("operand"))
    val = _coerce_interval(val)
    return val.low if isinstance(val, Interval) else None


def _op_ends_included_in(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    """``A ends during B`` — A's end is contained in interval B."""
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if a is None or b is None:
        return None
    a_end = a.high if isinstance(a, Interval) else a
    if a_end is None:
        return None
    if not isinstance(b, Interval):
        return None
    try:
        low_ok = b.low is None or b.low <= a_end
        high_ok = b.high is None or a_end <= b.high
        return low_ok and high_ok
    except TypeError:
        return None


def _op_starts_included_in(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    """``A starts during B`` — A's start is contained in interval B."""
    a, b = _operands(ctx, node)
    a = _coerce_interval(a)
    b = _coerce_interval(b)
    if a is None or b is None:
        return None
    a_start = a.low if isinstance(a, Interval) else a
    if a_start is None:
        return None
    if not isinstance(b, Interval):
        return None
    try:
        low_ok = b.low is None or b.low <= a_start
        high_ok = b.high is None or a_start <= b.high
        return low_ok and high_ok
    except TypeError:
        return None


def _coerce_interval(value: Any) -> Any:
    """Best-effort coercion of FHIR Period dicts to :class:`Interval`."""
    if (
        isinstance(value, dict)
        and ("start" in value or "end" in value)
        and "resourceType" not in value
    ):
        return Interval(
            low=_parse_dt(value.get("start")),
            high=_parse_dt(value.get("end")),
        )
    return value


def _op_in(ctx: RuntimeContext, node: ElmNode) -> bool | None:
    a, b = _operands(ctx, node)
    if b is None:
        return None
    if isinstance(b, ValueSetRef):
        if ctx.terminology is None:
            return None
        code = _to_code(a)
        if code is None:
            return None
        return ctx.terminology.in_value_set(code, b)
    if isinstance(b, Interval):
        if a is None:
            return None
        try:
            return b.contains(a)
        except TypeError:
            return None
    if isinstance(b, list):
        return a in b
    return None


# --- references -----------------------------------------------------------


def _op_expression_ref(ctx: RuntimeContext, node: ElmNode) -> Any:
    name = node.get("name")
    if not isinstance(name, str):
        return None
    lib_name = node.get("libraryName")
    if lib_name:
        return _resolve_cross_library(ctx, lib_name, name)
    # If the name doesn't match any statement in the current library, it may
    # be a bare property reference inside a sort/return expression where the
    # implicit ``$this`` is the current sort element. Fall back to looking
    # the name up as a property of the single active alias.
    if ctx.library is not None and name not in ctx.library.definitions:
        prop = _lookup_property_on_current_alias(ctx, name)
        if prop is not None:
            return prop
    return ctx.evaluate_definition(name)


def _lookup_property_on_current_alias(ctx: RuntimeContext, name: str) -> Any:
    stack = getattr(ctx, "_alias_stack", None)
    if not stack:
        return None
    frame = stack[-1]
    if len(frame) != 1:
        return None
    only_value = next(iter(frame.values()))
    return _fhir_property(only_value, name)


def _op_parameter_ref(ctx: RuntimeContext, node: ElmNode) -> Any:
    name = node.get("name")
    if not isinstance(name, str):
        return None
    if name in ctx.parameters:
        return ctx.parameters[name]
    if ctx.library is not None and name in ctx.library.parameters:
        return _eval_child(ctx, ctx.library.parameters[name].payload.get("default"))
    return None


def _op_alias_ref(ctx: RuntimeContext, node: ElmNode) -> Any:
    name = node.get("name")
    if not isinstance(name, str):
        return None
    try:
        return ctx.lookup_alias(name)
    except KeyError:
        return None


def _op_aliased_query_source(ctx: RuntimeContext, node: ElmNode) -> Any:
    return _eval_child(ctx, node.get("expression"))


def _op_query_let_ref(ctx: RuntimeContext, node: ElmNode) -> Any:
    name = node.get("name")
    if not isinstance(name, str):
        return None
    try:
        return ctx.lookup_let(name)
    except KeyError:
        return None


def _op_code_ref(ctx: RuntimeContext, node: ElmNode) -> Code | None:
    name = node.get("name")
    if not isinstance(name, str) or ctx.library is None:
        return None
    lib_name = node.get("libraryName")
    if lib_name:
        return _resolve_code_ref_cross_library(ctx, lib_name, name)
    defn = ctx.library.codes.get(name)
    if defn is None:
        return None
    cs_field = defn.get("codeSystem")
    cs_name = cs_field.get("name") if isinstance(cs_field, dict) else None
    cs_uri: str | None = None
    if cs_name and ctx.library:
        cs_def = ctx.library.code_systems.get(cs_name)
        if cs_def:
            cs_uri = cs_def.get("id")
    return Code(code=str(defn.get("id", "")), system=cs_uri, display=defn.get("display"))


def _op_code_system_ref(ctx: RuntimeContext, node: ElmNode) -> str | None:
    name = node.get("name")
    if not isinstance(name, str) or ctx.library is None:
        return None
    defn = ctx.library.code_systems.get(name)
    return defn.get("id") if defn else None


def _op_value_set_ref(ctx: RuntimeContext, node: ElmNode) -> ValueSetRef | None:
    name = node.get("name")
    if not isinstance(name, str) or ctx.library is None:
        return None
    defn = ctx.library.value_sets.get(name)
    if defn is None:
        return None
    return ValueSetRef(id=str(defn.get("id", "")), version=defn.get("version"))


def _op_code(ctx: RuntimeContext, node: ElmNode) -> Code:
    """Inline Code literal."""
    cs_field = node.get("system")
    cs_name = cs_field.get("name") if isinstance(cs_field, dict) else None
    cs_uri: str | None = None
    if cs_name and ctx.library:
        cs_def = ctx.library.code_systems.get(cs_name)
        if cs_def:
            cs_uri = cs_def.get("id")
    return Code(code=str(node.get("code", "")), system=cs_uri, display=node.get("display"))


# --- FHIR / null aware ---------------------------------------------------


def _op_as(ctx: RuntimeContext, node: ElmNode) -> Any:
    """Type cast: mostly pass-through, with select FHIR coercions."""
    operand = _eval_child(ctx, node.get("operand"))
    as_type_spec = node.get("asTypeSpecifier")
    as_type_name = ""
    if isinstance(as_type_spec, dict):
        as_type_name = str(as_type_spec.get("name") or "")
    if not as_type_name:
        as_type_name = str(node.get("asType") or "")

    if operand is None:
        return None
    if "Quantity" in as_type_name and isinstance(operand, dict) and "value" in operand:
        return _fhir_dict_to_quantity(operand)
    if ("DateTime" in as_type_name or "Date" in as_type_name) and isinstance(operand, str):
        return _parse_dt(operand)
    if (
        "Period" in as_type_name
        and isinstance(operand, dict)
        and ("start" in operand or "end" in operand)
    ):
        return Interval(low=_parse_dt(operand.get("start")), high=_parse_dt(operand.get("end")))
    return operand


def _op_is_null(ctx: RuntimeContext, node: ElmNode) -> bool:
    return _eval_child(ctx, node.get("operand")) is None


def _op_property(ctx: RuntimeContext, node: ElmNode) -> Any:
    """Read a FHIR / nested property, with choice-type expansion."""
    source_expr = node.get("source")
    scope = node.get("scope")
    if source_expr is not None:
        source = _eval_child(ctx, source_expr)
    elif isinstance(scope, str):
        try:
            source = ctx.lookup_alias(scope)
        except KeyError:
            source = None
    else:
        source = None
    path = node.get("path")
    if source is None or not isinstance(path, str):
        return None
    return _fhir_property(source, path)


def _op_to_concept(ctx: RuntimeContext, node: ElmNode) -> Any:
    val = _eval_child(ctx, node.get("operand"))
    return _wrap_as_concept(val)


def _op_to_string(ctx: RuntimeContext, node: ElmNode) -> str | None:
    val = _eval_child(ctx, node.get("operand"))
    return None if val is None else str(val)


# --- Retrieve / Query / FunctionRef --------------------------------------


def _op_retrieve(ctx: RuntimeContext, node: ElmNode) -> list[Any]:
    data_type = str(node.get("dataType") or "")
    short = data_type.split("}", 1)[-1] if "}" in data_type else data_type.rsplit(":", 1)[-1]
    short = short.split(".", 1)[-1]
    code_property = node.get("codeProperty")
    codes_expr = node.get("codes")
    code_values: Any = None
    if codes_expr is not None:
        code_values = _eval_child(ctx, codes_expr)
    if ctx.data_source is None:
        return []
    rows = ctx.data_source.retrieve(
        data_type=short,
        code_property=code_property,
        codes=code_values,
        context=ctx,
    )
    return list(rows)


def _op_query(ctx: RuntimeContext, node: ElmNode) -> Any:
    sources = node.get("source") or []
    if not isinstance(sources, list):
        sources = [sources]
    if not sources:
        return []

    alias_pairs: list[tuple[str, list[Any]]] = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        alias_name = str(src.get("alias", ""))
        expr = src.get("expression")
        items = _eval_child(ctx, expr)
        if items is None:
            items = []
        if not isinstance(items, list):
            items = [items]
        alias_pairs.append((alias_name, items))

    where_node = node.get("where")
    sort_node = node.get("sort") if isinstance(node.get("sort"), dict) else None
    return_node = node.get("return") if isinstance(node.get("return"), dict) else None
    let_nodes = node.get("let") or []

    def iter_combinations(idx: int, frame: dict[str, Any]) -> Iterator[dict[str, Any]]:
        if idx == len(alias_pairs):
            yield dict(frame)
            return
        name, items = alias_pairs[idx]
        for item in items:
            frame[name] = item
            yield from iter_combinations(idx + 1, frame)
            del frame[name]

    filtered: list[dict[str, Any]] = []
    for combo in iter_combinations(0, {}):
        ctx.push_alias_frame(combo)
        let_frame: dict[str, Any] = {}
        if let_nodes:
            for ld in let_nodes:
                if isinstance(ld, dict) and "identifier" in ld:
                    let_frame[ld["identifier"]] = _eval_child(ctx, ld.get("expression"))
            ctx.push_let_frame(let_frame)
        try:
            keep = True
            if where_node is not None:
                keep = _eval_child(ctx, where_node) is True
            if keep:
                filtered.append(dict(combo))
        finally:
            if let_nodes:
                ctx.pop_let_frame()
            ctx.pop_alias_frame()

    if sort_node:
        by = sort_node.get("by") or []
        single_alias = alias_pairs[0][0] if len(alias_pairs) == 1 else None

        def make_key(sd: dict[str, Any]) -> tuple[Callable[[dict[str, Any]], Any], str]:
            expr = sd.get("expression")
            path = sd.get("path")
            direction = sd.get("direction", "asc")

            def key_for(combo: dict[str, Any]) -> Any:
                ctx.push_alias_frame(combo)
                try:
                    if isinstance(expr, dict):
                        return _eval_child(ctx, expr)
                    if isinstance(path, str) and single_alias is not None:
                        return _fhir_property(combo[single_alias], path)
                    return None
                finally:
                    ctx.pop_alias_frame()

            return key_for, direction

        def sort_key_for(
            combo: dict[str, Any],
            key_fn: Callable[[dict[str, Any]], Any],
        ) -> tuple[bool, Any]:
            value = key_fn(combo)
            return (value is None, _to_sortable(value))

        for sd in reversed(by):
            if not isinstance(sd, dict):
                continue
            key_for, direction = make_key(sd)
            filtered.sort(
                key=partial(sort_key_for, key_fn=key_for),
                reverse=(direction == "desc"),
            )

    if return_node:
        expr = return_node.get("expression")
        result: list[Any] = []
        for combo in filtered:
            ctx.push_alias_frame(combo)
            try:
                result.append(_eval_child(ctx, expr))
            finally:
                ctx.pop_alias_frame()
        return result

    if len(alias_pairs) == 1:
        single_alias = alias_pairs[0][0]
        return [combo[single_alias] for combo in filtered]
    return filtered


def _op_function_ref(ctx: RuntimeContext, node: ElmNode) -> Any:
    name = str(node.get("name") or "")
    lib_name = node.get("libraryName")
    args = node.get("operand") or []

    # Fluent FHIR helper: `<resource>.extension(<url>)` — the CQL parser
    # accepts both `'url'` (string literal) and `"url"` (quoted identifier)
    # forms for the url argument. The latter is emitted as an ExpressionRef,
    # which would otherwise blow up with a missing-definition error. Pull the
    # url as a string directly from either shape, then look up the matching
    # FHIR extension by url on the receiver.
    if not lib_name and name == "extension" and len(args) == 2:
        receiver = _eval_child(ctx, args[0])
        url_node = args[1]
        url: Any
        if isinstance(url_node, dict):
            node_type = url_node.get("type")
            if node_type == "Literal":
                url = url_node.get("value")
            elif node_type in ("ExpressionRef", "FunctionRef"):
                url = url_node.get("name")
            else:
                url = _eval_child(ctx, url_node)
        else:
            url = _eval_child(ctx, url_node)
        return _fhir_extension_lookup(receiver, url)

    arg_vals = [_eval_child(ctx, a) for a in args]

    if lib_name in ("FHIRHelpers", "Global"):
        result = _fhirhelpers_call(name, arg_vals)
        if result is not _UNSUPPORTED:
            return result

    if lib_name and ctx.library_registry is not None:
        target_id = _find_included_library(ctx, lib_name)
        if target_id and ctx.library_registry.has(target_id):
            return ctx.evaluate_in_library(target_id, name)

    if ctx.library is not None and ctx.library.has_definition(name):
        return ctx.evaluate_definition(name)

    return arg_vals[0] if arg_vals else None


def _fhir_extension_lookup(receiver: Any, url: Any) -> Any:
    """Return the first FHIR extension on ``receiver`` whose ``url`` matches.

    Supports both fully-qualified URLs (``http://...``) and bare short names
    (``present-on-admission``); for the latter we match on the URL suffix.
    """
    if receiver is None or not isinstance(url, str) or not url:
        return None
    candidates: list[Any] = []
    if isinstance(receiver, dict):
        ext = receiver.get("extension")
        if isinstance(ext, list):
            candidates = ext
    else:
        attr = getattr(receiver, "extension", None)
        if isinstance(attr, list):
            candidates = attr
    for entry in candidates:
        entry_url: Any = (
            entry.get("url") if isinstance(entry, dict) else getattr(entry, "url", None)
        )
        if not isinstance(entry_url, str):
            continue
        if entry_url == url or entry_url.rsplit("/", 1)[-1] == url:
            return entry
    return None


# --- registry wiring ------------------------------------------------------


def register_builtins(registry: DefaultOperatorRegistry) -> None:
    """Populate ``registry`` with the built-in operator set."""
    ops: dict[str, OperatorFn] = {
        # literals + null
        "Literal": _op_literal,
        "Null": _op_null,
        "IsNull": _op_is_null,
        "As": _op_as,
        "Property": _op_property,
        # arithmetic
        "Add": _op_add,
        "Subtract": _op_sub,
        "Multiply": _op_mul,
        "Divide": _op_div,
        "TruncatedDivide": _op_div,
        "Negate": _op_negate,
        # comparison
        "Equal": _op_equal,
        "NotEqual": _op_not_equal,
        "Equivalent": _op_equivalent,
        "Greater": _op_greater,
        "GreaterOrEqual": _op_greater_or_equal,
        "Less": _op_less,
        "LessOrEqual": _op_less_or_equal,
        # boolean
        "And": _op_and,
        "Or": _op_or,
        "Xor": _op_xor,
        "Not": _op_not,
        "If": _op_if,
        "Case": _op_case,
        # aggregates / control
        "List": _op_list,
        "ToList": _op_to_list,
        "Tuple": _op_tuple,
        "Instance": _op_tuple,
        "Interval": _op_interval,
        # list/collection
        "Exists": _op_exists,
        "SingletonFrom": _op_singleton_from,
        "First": _op_first,
        "Last": _op_last,
        "Count": _op_count,
        "Length": _op_length,
        "Flatten": _op_flatten,
        "Coalesce": _op_coalesce,
        # quantity
        "Quantity": _op_quantity,
        # date / time / age
        "Date": _op_date,
        "DateTime": _op_datetime,
        "DateFrom": _op_date_from,
        "CalculateAge": _op_calculate_age,
        "CalculateAgeAt": _op_calculate_age_at,
        # interval / membership
        "Start": _op_start,
        "End": _op_end,
        "Ends": _op_ends,
        "Starts": _op_starts,
        "Overlaps": _op_overlaps,
        "IncludedIn": _op_included_in,
        "EndsIncludedIn": _op_ends_included_in,
        "StartsIncludedIn": _op_starts_included_in,
        "Includes": _op_includes,
        "Before": _op_before,
        "After": _op_after,
        "In": _op_in,
        # references
        "ExpressionRef": _op_expression_ref,
        "ParameterRef": _op_parameter_ref,
        "AliasRef": _op_alias_ref,
        "AliasedQuerySource": _op_aliased_query_source,
        "LetClause": _op_aliased_query_source,
        "QueryLetRef": _op_query_let_ref,
        "CodeRef": _op_code_ref,
        "CodeSystemRef": _op_code_system_ref,
        "ValueSetRef": _op_value_set_ref,
        "ConceptRef": _op_code_ref,
        "Code": _op_code,
        # retrieve / query / function dispatch
        "Retrieve": _op_retrieve,
        "Query": _op_query,
        "FunctionRef": _op_function_ref,
        # FHIR coercions
        "ToConcept": _op_to_concept,
        "ToString": _op_to_string,
    }
    for k, v in ops.items():
        registry.register(k, v)


# --- support utilities ---------------------------------------------------


def _combine_or(a: Any, b: Any) -> Any:
    if a is True or b is True:
        return True
    if a is None or b is None:
        return None
    return bool(a or b)


def _to_sortable(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


_UNSUPPORTED = object()


def _fhirhelpers_call(name: str, args: list[Any]) -> Any:
    """Map common FHIRHelpers / Global function calls to native coercions."""
    if not args:
        return None
    first = args[0]
    if name in ("ToString", "ToValue"):
        return str(first) if first is not None else None
    if name in ("ToDateTime", "ToDate"):
        if isinstance(first, str):
            return _parse_dt(first)
        if isinstance(first, dict) and "start" in first:
            return _parse_dt(first.get("start"))
        return first
    if name == "ToQuantity":
        if isinstance(first, dict) and "value" in first:
            return _fhir_dict_to_quantity(first)
        return first
    if name == "ToConcept":
        return _wrap_as_concept(first)
    if name == "ToInterval":
        if isinstance(first, dict) and ("start" in first or "end" in first):
            return Interval(low=_parse_dt(first.get("start")), high=_parse_dt(first.get("end")))
        return first
    if name == "ToCode":
        if isinstance(first, dict):
            return Code(
                code=str(first.get("code", "")),
                system=first.get("system"),
                display=first.get("display"),
                version=first.get("version"),
            )
        return first
    if name == "ToBoolean":
        if isinstance(first, str):
            return first.lower() == "true"
        return bool(first) if first is not None else None
    return _UNSUPPORTED


def _wrap_as_concept(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, list):
        return {"coding": [_code_to_coding(c) for c in val if c is not None]}
    return {"coding": [_code_to_coding(val)]}


def _code_to_coding(code: Any) -> dict[str, Any]:
    if isinstance(code, Code):
        return {
            "code": code.code,
            "system": code.system,
            "display": code.display,
            "version": code.version,
        }
    if isinstance(code, dict):
        if "code" in code and "system" in code:
            return code
        if "coding" in code and isinstance(code["coding"], list) and code["coding"]:
            first = code["coding"][0]
            if isinstance(first, dict):
                return first
    return {"code": str(code)}


def _to_code(value: Any) -> Code | None:
    if value is None:
        return None
    if isinstance(value, Code):
        return value
    if isinstance(value, dict):
        if "code" in value and "system" in value:
            return Code(
                code=value["code"],
                system=value.get("system"),
                display=value.get("display"),
            )
        coding = value.get("coding")
        if isinstance(coding, list) and coding:
            first = coding[0]
            if isinstance(first, dict):
                return Code(
                    code=first.get("code", ""),
                    system=first.get("system"),
                    display=first.get("display"),
                )
    if isinstance(value, str):
        return Code(code=value, system=None)
    return None


def _fhir_property(source: Any, path: str) -> Any:
    if source is None:
        return None
    if isinstance(source, list):
        return [_fhir_property(s, path) for s in source]
    if isinstance(source, dict):
        if path in source:
            return _coerce_fhir_value(source[path], path)
        for suffix in _FHIR_CHOICE_SUFFIXES:
            key = path + suffix
            if key in source:
                return _coerce_fhir_value(source[key], key)
        return None
    return getattr(source, path, None)


_FHIR_CHOICE_SUFFIXES = (
    "DateTime",
    "Date",
    "Period",
    "Quantity",
    "Range",
    "Ratio",
    "Reference",
    "CodeableConcept",
    "Coding",
    "Boolean",
    "String",
    "Integer",
    "Decimal",
    "Time",
    "Age",
    "Duration",
    "Attachment",
    "Identifier",
    "HumanName",
    "Annotation",
    "Money",
    "ContactPoint",
    "Address",
)


def _coerce_fhir_value(value: Any, key_or_path: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        if "start" in value or "end" in value:
            return Interval(low=_parse_dt(value.get("start")), high=_parse_dt(value.get("end")))
        if "value" in value and ("unit" in value or "code" in value):
            return _fhir_dict_to_quantity(value)
        return value
    if isinstance(value, str):
        if (
            key_or_path.endswith("DateTime")
            or key_or_path.endswith("Date")
            or _looks_iso_date(value)
        ):
            return _parse_dt(value)
        return value
    return value


def _fhir_dict_to_quantity(q: dict[str, Any]) -> Quantity:
    unit = q.get("code") or q.get("unit") or "1"
    return Quantity(value=Decimal(str(q.get("value", 0))), unit=str(unit))


def _looks_iso_date(s: str) -> bool:
    return len(s) >= 8 and s[:4].isdigit() and s[4] == "-"


def _parse_dt(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    if "T" in value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    try:
        return date.fromisoformat(value)
    except ValueError:
        return value


def _shift_date(d: Any, q: Quantity, sign: int) -> Any:
    """Add/subtract a calendar :class:`Quantity` to/from a date or datetime."""
    if d is None or q is None:
        return None
    try:
        n = int(q.value) * sign
    except (TypeError, ValueError):
        return None
    unit = (q.unit or "").lower()
    if unit in ("year", "years", "a"):
        return d + relativedelta(years=n)
    if unit in ("month", "months", "mo"):
        return d + relativedelta(months=n)
    if unit in ("week", "weeks", "wk"):
        return d + relativedelta(weeks=n)
    if unit in ("day", "days", "d"):
        return d + relativedelta(days=n)
    if unit in ("hour", "hours", "h"):
        return d + relativedelta(hours=n)
    if unit in ("minute", "minutes", "min"):
        return d + relativedelta(minutes=n)
    if unit in ("second", "seconds", "s"):
        return d + relativedelta(seconds=n)
    return d


def _age_in(birth: Any, asof: Any, precision: str) -> int | None:
    if isinstance(birth, str):
        birth = _parse_dt(birth)
    if isinstance(asof, str):
        asof = _parse_dt(asof)
    if isinstance(birth, datetime):
        birth = birth.date()
    if isinstance(asof, datetime):
        asof = asof.date()
    if not isinstance(birth, date) or not isinstance(asof, date):
        return None
    if precision == "year":
        years = asof.year - birth.year
        if (asof.month, asof.day) < (birth.month, birth.day):
            years -= 1
        return years
    if precision == "month":
        months = (asof.year - birth.year) * 12 + (asof.month - birth.month)
        if asof.day < birth.day:
            months -= 1
        return months
    if precision in ("day", "days"):
        return (asof - birth).days
    return asof.year - birth.year


def _resolve_cross_library(ctx: RuntimeContext, lib_name: str, def_name: str) -> Any:
    target = _find_included_library(ctx, lib_name)
    if target is None and lib_name == "Global":
        target = _find_included_library(ctx, "FHIRHelpers")
    if target is None or ctx.library_registry is None or not ctx.library_registry.has(target):
        return None
    other = ctx.library_registry.get(target)
    # Prefer statement defs, fall back to named codes/value sets/code systems.
    if def_name in other.definitions:
        return ctx.evaluate_in_library(target, def_name)
    if def_name in other.codes:
        return _resolve_code_ref_cross_library(ctx, lib_name, def_name)
    if def_name in other.value_sets:
        vs = other.value_sets[def_name]
        from cql_sdk.abstractions.terminology import ValueSetRef as _VSR

        return _VSR(id=str(vs.get("id") or def_name))
    return None


def _resolve_code_ref_cross_library(
    ctx: RuntimeContext, lib_name: str, code_name: str
) -> Code | None:
    target = _find_included_library(ctx, lib_name)
    if target is None and lib_name == "Global":
        target = _find_included_library(ctx, "FHIRHelpers")
    if target is None or ctx.library_registry is None or not ctx.library_registry.has(target):
        return None
    other = ctx.library_registry.get(target)
    defn = other.codes.get(code_name)
    if defn is None:
        return None
    cs_field = defn.get("codeSystem")
    cs_name = cs_field.get("name") if isinstance(cs_field, dict) else None
    cs_uri: str | None = None
    if cs_name:
        cs_def = other.code_systems.get(cs_name)
        if cs_def:
            cs_uri = cs_def.get("id")
    return Code(code=str(defn.get("id", "")), system=cs_uri, display=defn.get("display"))


def _find_included_library(ctx: RuntimeContext, alias_or_id: str) -> str | None:
    if ctx.library is None:
        return alias_or_id
    raw = ctx.library.raw
    body = raw.get("library", raw) if isinstance(raw, dict) else {}
    includes = (
        body.get("includes", {}).get("def", [])
        if isinstance(body.get("includes"), dict)
        else []
    )
    for inc in includes:
        if not isinstance(inc, dict):
            continue
        if inc.get("localIdentifier") == alias_or_id or inc.get("path") == alias_or_id:
            return str(inc.get("path") or inc.get("localIdentifier"))
    if ctx.library_registry is not None and ctx.library_registry.has(alias_or_id):
        return alias_or_id
    return None
