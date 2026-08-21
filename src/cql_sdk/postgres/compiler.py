"""Compile loaded CQL/ELM libraries into parameterized PostgreSQL SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from cql_sdk.elm.models.base import ElmNode
from cql_sdk.elm.models.library import Library

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UnsupportedElmError(ValueError):
    """Raised when an ELM node cannot be represented safely in SQL."""


@dataclass(frozen=True, slots=True)
class CompiledQuery:
    """A SQL statement and its positional bind parameters."""

    sql: str
    parameters: tuple[Any, ...]
    definition: str


@dataclass(slots=True)
class _Fragment:
    sql: str
    parameters: list[Any] = field(default_factory=list)
    kind: Literal["scalar", "relation"] = "scalar"
    value_type: str = "unknown"
    order_columns: list[tuple[str, str]] = field(default_factory=list)


class PostgresCompiler:
    """Translate an ELM definition into SQL over the SDK FHIR JSONB schema."""

    def __init__(
        self,
        library: Library,
        *,
        parameters: dict[str, Any] | None = None,
        patient_id: str | None = None,
        schema: str = "public",
    ) -> None:
        self.library = library
        self.parameters = parameters or {}
        self.patient_id = patient_id
        self.schema = _validated_identifier(schema, "schema")
        self._definition_stack: list[str] = []
        self._alias_counter = 0

    def compile(self, definition: str) -> CompiledQuery:
        """Compile ``definition`` to one result-row SQL statement."""
        fragment = self._compile_definition(definition, {})
        if fragment.kind == "relation":
            sql = (
                "SELECT COALESCE(jsonb_agg(compiled_rows.value), '[]'::jsonb) AS result "
                f"FROM ({fragment.sql}) AS compiled_rows"
            )
        else:
            sql = f"SELECT {fragment.sql} AS result"
        return CompiledQuery(sql=sql, parameters=tuple(fragment.parameters), definition=definition)

    @property
    def _resources_table(self) -> str:
        return f'"{self.schema}"."fhir_resources"'

    @property
    def _terminology_table(self) -> str:
        return f'"{self.schema}"."terminology_codes"'

    def _next_alias(self, prefix: str) -> str:
        self._alias_counter += 1
        return f"{prefix}_{self._alias_counter}"

    def _compile_definition(
        self,
        name: str,
        aliases: dict[str, _Fragment],
    ) -> _Fragment:
        if name in self._definition_stack:
            chain = " -> ".join([*self._definition_stack, name])
            raise UnsupportedElmError(f"Cyclic definition reference: {chain}")
        if not self.library.has_definition(name):
            if name == "Patient":
                return self._patient_resource()
            raise KeyError(f"Definition '{name}' not found in library '{self.library.identifier}'.")
        self._definition_stack.append(name)
        try:
            node = self.library.get_definition(name).expression
            return self._compile_node(node, aliases)
        finally:
            self._definition_stack.pop()

    def _compile_node(
        self,
        raw: ElmNode | dict[str, Any] | None,
        aliases: dict[str, _Fragment],
    ) -> _Fragment:
        if raw is None:
            return _Fragment("NULL", value_type="null")
        node = raw if isinstance(raw, ElmNode) else ElmNode.from_json(raw)
        node_type = node.type

        if node_type == "Literal":
            return self._literal(node)
        if node_type == "Null":
            return _Fragment("NULL", value_type="null")
        if node_type == "Quantity":
            unit = str(node.get("unit") or "1").lower()
            return _Fragment(
                "%s",
                [Decimal(str(node.get("value")))],
                value_type=f"quantity:{unit}",
            )
        if node_type == "ExpressionRef":
            name = str(node.get("name") or "")
            if node.get("libraryName") in {"FHIRHelpers", "Global"}:
                return _Fragment("%s", [name], value_type="code")
            if not self.library.has_definition(name) and aliases:
                source = next(reversed(aliases.values()))
                return _Fragment(
                    f"jsonb_extract_path(({source.sql})::jsonb, %s)",
                    [*source.parameters, name],
                    value_type="jsonb",
                )
            return self._compile_definition(name, aliases)
        if node_type == "ParameterRef":
            return self._parameter(node, aliases)
        if node_type == "AliasRef":
            name = str(node.get("name") or "")
            try:
                return aliases[name]
            except KeyError as exc:
                raise UnsupportedElmError(f"Unknown SQL query alias '{name}'.") from exc
        if node_type == "Property":
            return self._property(node, aliases)
        if node_type == "Retrieve":
            return self._retrieve(node, aliases)
        if node_type == "Query":
            return self._query(node, aliases)
        if node_type == "Exists":
            return self._exists(node, aliases)
        if node_type in {"First", "Last", "SingletonFrom", "Count"}:
            return self._collection_operator(node, aliases)
        if node_type == "List":
            return self._list(node, aliases)
        if node_type == "Flatten":
            return self._flatten(node, aliases)
        if node_type == "ToList":
            operand = self._compile_node(node.get("operand"), aliases)
            if operand.kind == "relation":
                return operand
            return _Fragment(
                f"SELECT {operand.sql} AS value WHERE {operand.sql} IS NOT NULL",
                [*operand.parameters, *operand.parameters],
                kind="relation",
                value_type=operand.value_type,
            )
        if node_type in {"Add", "Subtract", "Multiply", "Divide", "TruncatedDivide"}:
            return self._arithmetic(node, aliases)
        if node_type in {
            "Equal",
            "Equivalent",
            "NotEqual",
            "Greater",
            "GreaterOrEqual",
            "Less",
            "LessOrEqual",
        }:
            return self._comparison(node, aliases)
        if node_type in {"And", "Or", "Xor"}:
            return self._boolean(node, aliases)
        if node_type == "Not":
            operand = self._compile_node(node.get("operand"), aliases)
            return _Fragment(f"NOT ({operand.sql})", operand.parameters, value_type="boolean")
        if node_type == "Negate":
            operand = self._compile_node(node.get("operand"), aliases)
            return _Fragment(f"-({operand.sql})", operand.parameters, value_type=operand.value_type)
        if node_type == "IsNull":
            operand = self._compile_node(node.get("operand"), aliases)
            return _Fragment(
                f"({operand.sql}) IS NULL",
                operand.parameters,
                value_type="boolean",
            )
        if node_type == "As":
            return self._cast(node, aliases)
        if node_type in {"ToConcept", "ToString"}:
            operands = self._operands(node, aliases)
            operand = operands[0] if operands else _Fragment("NULL", value_type="null")
            if node_type == "ToConcept" and operand.value_type in {"text", "code"}:
                operand.value_type = "concept_code"
            return operand
        if node_type == "FunctionRef":
            return self._function_ref(node, aliases)
        if node_type == "Interval":
            return self._interval(node, aliases)
        if node_type == "DurationBetween":
            return self._duration_between(node, aliases)
        if node_type in {
            "IncludedIn",
            "EndsIncludedIn",
            "StartsIncludedIn",
            "Overlaps",
            "Before",
            "After",
            "In",
        }:
            return self._interval_operator(node, aliases)
        if node_type in {"Start", "End", "DateFrom"}:
            return self._date_operator(node, aliases)
        if node_type in {"Date", "DateTime"}:
            return self._date_constructor(node, aliases)
        if node_type in {"CalculateAge", "CalculateAgeAt"}:
            return self._calculate_age(node, aliases)
        if node_type == "Coalesce":
            operands = self._operands(node, aliases)
            return _Fragment(
                f"COALESCE({', '.join(item.sql for item in operands)})",
                [value for item in operands for value in item.parameters],
                value_type=next(
                    (item.value_type for item in operands if item.value_type != "null"),
                    "unknown",
                ),
            )
        if node_type == "If":
            condition = self._compile_node(node.get("condition"), aliases)
            then = self._compile_node(node.get("then"), aliases)
            otherwise = self._compile_node(node.get("else"), aliases)
            return _Fragment(
                f"CASE WHEN {condition.sql} THEN {then.sql} ELSE {otherwise.sql} END",
                [*condition.parameters, *then.parameters, *otherwise.parameters],
                value_type=then.value_type,
            )
        if node_type == "ValueSetRef":
            value_set = self._value_set(node)
            return _Fragment("%s", [value_set[0]], value_type="value_set")

        raise UnsupportedElmError(
            f"ELM node '{node_type}' is not supported by PostgreSQL execution."
        )

    def _literal(self, node: ElmNode) -> _Fragment:
        value = node.get("value")
        value_type = str(node.get("valueType") or "")
        if value is None:
            return _Fragment("NULL", value_type="null")
        if value_type.endswith("Integer"):
            return _Fragment("%s", [int(value)], value_type="numeric")
        if value_type.endswith("Decimal"):
            return _Fragment("%s", [Decimal(str(value))], value_type="numeric")
        if value_type.endswith("Boolean"):
            return _Fragment("%s", [str(value).lower() == "true"], value_type="boolean")
        return _Fragment("%s", [value], value_type="text")

    def _parameter(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        name = str(node.get("name") or "")
        if name in self.parameters:
            return self._bound_value(self.parameters[name])
        parameter = self.library.parameters.get(name)
        default = parameter.get("default") if parameter is not None else None
        if isinstance(default, dict):
            return self._compile_node(default, aliases)
        return _Fragment("NULL", value_type="null")

    def _bound_value(self, value: Any) -> _Fragment:
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return _Fragment(
                "tstzrange(%s::timestamptz, %s::timestamptz, '[]')",
                [value[0], value[1]],
                value_type="range",
            )
        if hasattr(value, "low") and hasattr(value, "high"):
            return _Fragment(
                "tstzrange(%s::timestamptz, %s::timestamptz, '[]')",
                [value.low, value.high],
                value_type="range",
            )
        if isinstance(value, bool):
            return _Fragment("%s", [value], value_type="boolean")
        if isinstance(value, (int, float, Decimal)):
            return _Fragment("%s", [value], value_type="numeric")
        if isinstance(value, datetime):
            return _Fragment("%s::timestamptz", [value], value_type="timestamp")
        if isinstance(value, date):
            return _Fragment("%s::date", [value], value_type="date")
        return _Fragment("%s", [value], value_type="text")

    def _property(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        source_raw = node.get("source")
        if source_raw is None and isinstance(node.get("scope"), str):
            source = aliases.get(str(node.get("scope")))
            if source is None:
                raise UnsupportedElmError(f"Unknown property scope '{node.get('scope')}'.")
        else:
            source = self._compile_node(source_raw, aliases)
        path = str(node.get("path") or "")
        segments = [segment for segment in path.split(".") if segment]
        if not segments:
            raise UnsupportedElmError("A Property node must include a path.")
        placeholders = ", ".join("%s" for _ in segments)
        if source.kind == "relation":
            relation_alias = self._next_alias("property")
            order_select = "".join(
                f", {relation_alias}.{column} AS {column}"
                for column, _ in source.order_columns
            )
            return _Fragment(
                "SELECT "
                f"jsonb_extract_path(({relation_alias}.value)::jsonb, {placeholders}) AS value"
                f"{order_select} FROM ({source.sql}) AS {relation_alias}",
                [*segments, *source.parameters],
                kind="relation",
                value_type="jsonb",
                order_columns=source.order_columns,
            )
        return _Fragment(
            f"jsonb_extract_path(({source.sql})::jsonb, {placeholders})",
            [*source.parameters, *segments],
            value_type="jsonb",
        )

    def _retrieve(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        del aliases
        data_type = str(node.get("dataType") or "")
        resource_type = (
            data_type.split("}", 1)[-1]
            if "}" in data_type
            else data_type.rsplit(":", 1)[-1]
        )
        resource_type = resource_type.split(".", 1)[-1]
        table_alias = self._next_alias("resource")
        predicates = [f"{table_alias}.resource_type = %s"]
        parameters: list[Any] = [resource_type]
        if self.patient_id is not None:
            id_column = "resource_id" if resource_type == "Patient" else "patient_id"
            predicates.append(f"{table_alias}.{id_column} = %s")
            parameters.append(self.patient_id)
        codes = node.get("codes")
        if isinstance(codes, dict):
            code_sql, code_parameters = self._code_filter(table_alias, node, codes)
            predicates.append(code_sql)
            parameters.extend(code_parameters)
        return _Fragment(
            f"SELECT {table_alias}.resource AS value FROM {self._resources_table} AS {table_alias} "
            f"WHERE {' AND '.join(predicates)}",
            parameters,
            kind="relation",
            value_type="jsonb",
        )

    def _code_filter(
        self,
        table_alias: str,
        retrieve: ElmNode,
        codes: dict[str, Any],
    ) -> tuple[str, list[Any]]:
        path = [part for part in str(retrieve.get("codeProperty") or "code").split(".") if part]
        placeholders = ", ".join("%s" for _ in path)
        code_source = f"jsonb_extract_path({table_alias}.resource, {placeholders})"
        code_type = str(codes.get("type") or "")
        if code_type == "ValueSetRef":
            value_set_url, version = self._value_set(ElmNode.from_json(codes))
            version_sql = ""
            parameters: list[Any] = [*path, value_set_url]
            if version:
                version_sql = " AND terminology.value_set_version IN ('', %s)"
                parameters.append(version)
            sql = (
                "EXISTS (SELECT 1 FROM "
                f"jsonb_path_query({code_source}, '$.**.coding[*]'::jsonpath) AS coding(value) "
                f"JOIN {self._terminology_table} AS terminology "
                "ON terminology.code = coding.value ->> 'code' "
                "AND (terminology.system = '' OR terminology.system = coding.value ->> 'system') "
                f"WHERE terminology.value_set_url = %s{version_sql})"
            )
            return sql, parameters
        code_node = codes.get("operand") if code_type == "ToList" else codes
        if isinstance(code_node, dict) and code_node.get("type") in {"CodeRef", "ConceptRef"}:
            code, system = self._code_ref(ElmNode.from_json(code_node))
            return (
                "EXISTS (SELECT 1 FROM "
                f"jsonb_path_query({code_source}, '$.**.coding[*]'::jsonpath) AS coding(value) "
                "WHERE coding.value ->> 'code' = %s "
                "AND (%s::text IS NULL OR coding.value ->> 'system' = %s::text))",
                [*path, code, system, system],
            )
        raise UnsupportedElmError(f"Retrieve code expression '{code_type}' is not supported.")

    def _query(self, node: ElmNode, outer_aliases: dict[str, _Fragment]) -> _Fragment:
        sources = node.get("source") or []
        if not isinstance(sources, list):
            sources = [sources]
        if not sources:
            return _Fragment("SELECT NULL::jsonb AS value WHERE FALSE", kind="relation")

        aliases = dict(outer_aliases)
        from_parts: list[str] = []
        source_parameters: list[Any] = []
        source_aliases: list[str] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            relation = self._compile_node(source.get("expression"), aliases)
            if relation.kind != "relation":
                relation = _Fragment(
                    f"SELECT {relation.sql} AS value",
                    relation.parameters,
                    kind="relation",
                    value_type=relation.value_type,
                )
            sql_alias = self._next_alias("source")
            source_aliases.append(sql_alias)
            aliases[str(source.get("alias") or "")] = _Fragment(
                f"{sql_alias}.value",
                value_type=relation.value_type,
            )
            join = " CROSS JOIN " if from_parts else ""
            from_parts.append(f"{join}({relation.sql}) AS {sql_alias}")
            source_parameters.extend(relation.parameters)

        return_node = node.get("return")
        if isinstance(return_node, dict) and isinstance(return_node.get("expression"), dict):
            selected = self._compile_node(return_node["expression"], aliases)
        else:
            selected = _Fragment(f"{source_aliases[0]}.value", value_type="jsonb")

        where = self._compile_node(node.get("where"), aliases) if node.get("where") else None
        sort_fragments: list[tuple[_Fragment, str, str]] = []
        sort = node.get("sort")
        if isinstance(sort, dict):
            for index, by in enumerate(sort.get("by") or []):
                if isinstance(by, dict) and isinstance(by.get("expression"), dict):
                    expression = self._compile_node(by["expression"], aliases)
                    direction = "DESC" if str(by.get("direction")).lower() == "desc" else "ASC"
                    sort_fragments.append((expression, direction, f"__cql_sort_{index}"))

        order_columns = [(column, direction) for _, direction, column in sort_fragments]
        if selected.kind == "relation":
            nested_alias = self._next_alias("lateral")
            sql = (
                f"SELECT {nested_alias}.value AS value FROM {''.join(from_parts)} "
                f"CROSS JOIN LATERAL ({selected.sql}) AS {nested_alias}"
            )
            parameters = [*source_parameters, *selected.parameters]
        else:
            sort_select = "".join(
                f", {fragment.sql} AS {column}"
                for fragment, _, column in sort_fragments
            )
            sql = f"SELECT {selected.sql} AS value{sort_select} FROM {''.join(from_parts)}"
            parameters = [
                *selected.parameters,
                *(value for fragment, _, _ in sort_fragments for value in fragment.parameters),
                *source_parameters,
            ]
        if where is not None:
            sql += f" WHERE {where.sql}"
            parameters.extend(where.parameters)
        if sort_fragments:
            sql += " ORDER BY " + ", ".join(
                f"{column} {direction}" for _, direction, column in sort_fragments
            )
        return _Fragment(
            sql,
            parameters,
            kind="relation",
            value_type=selected.value_type,
            order_columns=order_columns,
        )

    def _exists(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        operand = self._compile_node(node.get("operand"), aliases)
        if operand.kind == "relation":
            return _Fragment(
                f"EXISTS ({operand.sql})",
                operand.parameters,
                value_type="boolean",
            )
        if operand.value_type == "array":
            return _Fragment(
                f"cardinality({operand.sql}) > 0",
                operand.parameters,
                value_type="boolean",
            )
        return _Fragment(
            f"({operand.sql}) IS NOT NULL",
            operand.parameters,
            value_type="boolean",
        )

    def _collection_operator(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        source = self._compile_node(node.get("source") or node.get("operand"), aliases)
        if source.kind != "relation":
            if node.type == "Count":
                return _Fragment(
                    f"CASE WHEN {source.sql} IS NULL THEN 0 ELSE 1 END",
                    source.parameters,
                    value_type="numeric",
                )
            return source
        if node.type == "Count":
            return _Fragment(
                f"(SELECT count(*) FROM ({source.sql}) AS counted_rows)",
                source.parameters,
                value_type="numeric",
            )
        if source.order_columns:
            order_by = ", ".join(
                f"selected_rows.{column} "
                f"{_reverse_direction(direction) if node.type == 'Last' else direction}"
                for column, direction in source.order_columns
            )
        else:
            direction = "DESC" if node.type == "Last" else "ASC"
            order_by = f"selected_rows.value {direction}"
        return _Fragment(
            f"(SELECT selected_rows.value FROM ({source.sql}) AS selected_rows "
            f"ORDER BY {order_by} LIMIT 1)",
            source.parameters,
            value_type=source.value_type,
        )

    def _list(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        elements = [
            self._compile_node(element, aliases)
            for element in node.get("element") or []
            if isinstance(element, dict)
        ]
        if not elements:
            return _Fragment("ARRAY[]::text[]", value_type="array")
        values = []
        parameters: list[Any] = []
        for element in elements:
            sql, element_parameters = self._scalar_text(element)
            values.append(f"({sql})::text")
            parameters.extend(element_parameters)
        return _Fragment(
            f"ARRAY[{', '.join(values)}]",
            parameters,
            value_type="array",
        )

    def _flatten(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        operand = self._compile_node(node.get("operand"), aliases)
        if operand.kind == "relation":
            return operand
        if operand.value_type == "jsonb":
            return _Fragment(
                "SELECT flattened.value FROM "
                f"jsonb_array_elements({operand.sql}) AS flattened(value)",
                operand.parameters,
                kind="relation",
                value_type="jsonb",
            )
        raise UnsupportedElmError("Flatten requires a SQL relation or JSONB array.")

    def _arithmetic(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        left, right = self._operands(node, aliases, expected=2)
        operator = {
            "Add": "+",
            "Subtract": "-",
            "Multiply": "*",
            "Divide": "/",
            "TruncatedDivide": "/",
        }[node.type]
        if (
            node.type in {"Add", "Subtract"}
            and left.value_type in {"date", "timestamp"}
            and right.value_type.startswith("quantity:")
        ):
            unit = _interval_unit(right.value_type.removeprefix("quantity:"))
            return _Fragment(
                f"({left.sql} {operator} ({right.sql} * INTERVAL '1 {unit}'))",
                [*left.parameters, *right.parameters],
                value_type=left.value_type,
            )
        right_sql = (
            f"NULLIF({right.sql}, 0)"
            if node.type in {"Divide", "TruncatedDivide"}
            else right.sql
        )
        sql = f"({left.sql} {operator} {right_sql})"
        if node.type == "TruncatedDivide":
            sql = f"trunc({sql})"
        return _Fragment(sql, [*left.parameters, *right.parameters], value_type="numeric")

    def _comparison(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        left, right = self._operands(node, aliases, expected=2)
        if node.type == "Equivalent" and left.value_type == "jsonb" and right.value_type in {
            "code",
            "concept_code",
            "text",
        }:
            return self._concept_equivalent(left, right)
        if node.type == "Equivalent" and right.value_type == "jsonb" and left.value_type in {
            "code",
            "concept_code",
            "text",
        }:
            return self._concept_equivalent(right, left)
        left_sql, left_parameters = self._comparison_value(left, right.value_type)
        right_sql, right_parameters = self._comparison_value(right, left.value_type)
        operator = {
            "Equal": "=",
            "Equivalent": "IS NOT DISTINCT FROM",
            "NotEqual": "<>",
            "Greater": ">",
            "GreaterOrEqual": ">=",
            "Less": "<",
            "LessOrEqual": "<=",
        }[node.type]
        return _Fragment(
            f"({left_sql} {operator} {right_sql})",
            [*left_parameters, *right_parameters],
            value_type="boolean",
        )

    def _comparison_value(self, fragment: _Fragment, other_type: str) -> tuple[str, list[Any]]:
        if fragment.value_type != "jsonb":
            return fragment.sql, fragment.parameters
        scalar = f"({fragment.sql} #>> '{{}}')"
        if other_type == "numeric" or other_type.startswith("quantity:"):
            scalar = f"NULLIF({scalar}, '')::numeric"
        elif other_type == "date":
            scalar = f"NULLIF({scalar}, '')::date"
        elif other_type == "timestamp":
            scalar = f"NULLIF({scalar}, '')::timestamptz"
        elif other_type == "boolean":
            scalar = f"NULLIF({scalar}, '')::boolean"
        return scalar, fragment.parameters

    def _concept_equivalent(self, value: _Fragment, expected: _Fragment) -> _Fragment:
        return _Fragment(
            "EXISTS (SELECT 1 FROM (SELECT "
            f"({value.sql})::jsonb AS value, ({expected.sql})::text AS expected"
            ") AS equivalent_value WHERE "
            "equivalent_value.value #>> '{}' = equivalent_value.expected OR "
            "equivalent_value.value ->> 'code' = equivalent_value.expected OR "
            "jsonb_path_exists(equivalent_value.value, "
            "'$.**.coding[*] ? (@.code == $expected)'::jsonpath, "
            "jsonb_build_object('expected', equivalent_value.expected)))",
            [*value.parameters, *expected.parameters],
            value_type="boolean",
        )

    def _boolean(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        operands = self._operands(node, aliases)
        operator = {"And": " AND ", "Or": " OR ", "Xor": " <> "}[node.type]
        return _Fragment(
            "(" + operator.join(f"({operand.sql})" for operand in operands) + ")",
            [value for operand in operands for value in operand.parameters],
            value_type="boolean",
        )

    def _cast(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        operand = self._compile_node(node.get("operand"), aliases)
        target = str(node.get("asType") or node.get("asTypeSpecifier") or "").lower()
        if "quantity" in target:
            if operand.value_type == "jsonb":
                return _Fragment(
                    f"NULLIF(({operand.sql}) ->> 'value', '')::numeric",
                    operand.parameters,
                    value_type="numeric",
                )
            return operand
        if "datetime" in target:
            sql, parameters = self._scalar_text(operand)
            return _Fragment(
                f"NULLIF({sql}, '')::timestamptz",
                parameters,
                value_type="timestamp",
            )
        if "date" in target:
            sql, parameters = self._scalar_text(operand)
            return _Fragment(f"NULLIF({sql}, '')::date", parameters, value_type="date")
        if "period" in target:
            return self._jsonb_period_range(operand)
        return operand

    def _function_ref(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        name = str(node.get("name") or "")
        raw_operands = node.get("operand") or []
        if not isinstance(raw_operands, list):
            raw_operands = [raw_operands]
        if name == "extension" and len(raw_operands) == 2:
            receiver = self._compile_node(raw_operands[0], aliases)
            url_node = raw_operands[1]
            url = None
            if isinstance(url_node, dict):
                url = url_node.get("value") or url_node.get("name")
            if not isinstance(url, str) or not url:
                raise UnsupportedElmError("FHIR extension() requires a literal URL.")
            return _Fragment(
                "(SELECT extension.value FROM jsonb_array_elements("
                f"COALESCE(({receiver.sql}) -> 'extension', '[]'::jsonb)"
                ") AS extension(value) WHERE extension.value ->> 'url' = %s OR "
                "regexp_replace(extension.value ->> 'url', '^.*/', '') = %s LIMIT 1)",
                [*receiver.parameters, url, url],
                value_type="jsonb",
            )
        raise UnsupportedElmError(
            f"FunctionRef '{name}' is not supported by PostgreSQL execution."
        )

    def _duration_between(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        start, end = self._operands(node, aliases, expected=2)
        precision = str(node.get("precision") or "millisecond").lower()
        divisor = {
            "millisecond": Decimal("0.001"),
            "second": Decimal(1),
            "minute": Decimal(60),
            "hour": Decimal(3600),
            "day": Decimal(86400),
            "week": Decimal(604800),
        }.get(precision)
        if divisor is None:
            raise UnsupportedElmError(
                f"DurationBetween precision '{precision}' is not supported."
            )
        return _Fragment(
            f"(EXTRACT(EPOCH FROM (({end.sql}) - ({start.sql}))) / %s)::numeric",
            [*end.parameters, *start.parameters, divisor],
            value_type="numeric",
        )

    def _interval(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        low = self._compile_node(node.get("low"), aliases)
        high = self._compile_node(node.get("high"), aliases)
        bounds = ("[" if node.get("lowClosed", True) else "(") + (
            "]" if node.get("highClosed", True) else ")"
        )
        return _Fragment(
            f"tstzrange(({low.sql})::timestamptz, ({high.sql})::timestamptz, '{bounds}')",
            [*low.parameters, *high.parameters],
            value_type="range",
        )

    def _interval_operator(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        left, right = self._operands(node, aliases, expected=2)
        if node.type == "In" and right.value_type == "array":
            left_sql, left_parameters = self._scalar_text(left)
            return _Fragment(
                f"({left_sql}) = ANY({right.sql})",
                [*left_parameters, *right.parameters],
                value_type="boolean",
            )
        if left.value_type == "jsonb":
            left = self._jsonb_period_range(left)
        if right.value_type == "jsonb":
            right = self._jsonb_period_range(right)
        if node.type == "IncludedIn":
            operator = "<@"
        elif node.type == "Overlaps":
            operator = "&&"
        elif node.type == "In":
            operator = "<@"
        elif node.type == "Before":
            left_sql = f"upper({left.sql})" if left.value_type == "range" else left.sql
            right_sql = f"lower({right.sql})" if right.value_type == "range" else right.sql
            return _Fragment(
                f"({left_sql}) < ({right_sql})",
                [*left.parameters, *right.parameters],
                value_type="boolean",
            )
        elif node.type == "After":
            left_sql = f"lower({left.sql})" if left.value_type == "range" else left.sql
            right_sql = f"upper({right.sql})" if right.value_type == "range" else right.sql
            return _Fragment(
                f"({left_sql}) > ({right_sql})",
                [*left.parameters, *right.parameters],
                value_type="boolean",
            )
        elif node.type == "EndsIncludedIn":
            return _Fragment(
                f"upper({left.sql}) <@ {right.sql}",
                [*left.parameters, *right.parameters],
                value_type="boolean",
            )
        else:
            return _Fragment(
                f"lower({left.sql}) <@ {right.sql}",
                [*left.parameters, *right.parameters],
                value_type="boolean",
            )
        return _Fragment(
            f"({left.sql}) {operator} ({right.sql})",
            [*left.parameters, *right.parameters],
            value_type="boolean",
        )

    def _date_operator(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        operand = self._compile_node(node.get("operand"), aliases)
        if node.type == "DateFrom":
            sql, parameters = (
                self._scalar_text(operand)
                if operand.value_type == "jsonb"
                else (operand.sql, operand.parameters)
            )
            return _Fragment(f"({sql})::date", parameters, value_type="date")
        if operand.value_type == "jsonb":
            operand = self._jsonb_period_range(operand)
        function = "lower" if node.type == "Start" else "upper"
        return _Fragment(f"{function}({operand.sql})", operand.parameters, value_type="timestamp")

    def _date_constructor(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        fields = ["year", "month", "day"]
        parts = [
            self._compile_node(node.get(field), aliases)
            if node.get(field)
            else _Fragment("%s", [1], value_type="numeric")
            for field in fields
        ]
        if node.type == "Date":
            return _Fragment(
                f"make_date(({parts[0].sql})::int, ({parts[1].sql})::int, ({parts[2].sql})::int)",
                [value for part in parts for value in part.parameters],
                value_type="date",
            )
        time_parts = [
            self._compile_node(node.get(field), aliases)
            if node.get(field)
            else _Fragment("%s", [0], value_type="numeric")
            for field in ("hour", "minute", "second")
        ]
        all_parts = [*parts, *time_parts]
        return _Fragment(
            "make_timestamptz("
            + ", ".join(f"({part.sql})::int" for part in all_parts)
            + ", 'UTC')",
            [value for part in all_parts for value in part.parameters],
            value_type="timestamp",
        )

    def _calculate_age(self, node: ElmNode, aliases: dict[str, _Fragment]) -> _Fragment:
        operands = self._operands(node, aliases)
        if node.type == "CalculateAgeAt" and len(operands) >= 2:
            birth, as_of = operands[0], operands[1]
        elif node.type == "CalculateAgeAt" and operands:
            birth, as_of = self._patient_birth_date(), operands[0]
        elif operands:
            birth, as_of = operands[0], _Fragment("CURRENT_DATE", value_type="date")
        else:
            birth, as_of = self._patient_birth_date(), _Fragment("CURRENT_DATE", value_type="date")
        return _Fragment(
            f"EXTRACT(YEAR FROM age(({as_of.sql})::date, ({birth.sql})::date))::integer",
            [*as_of.parameters, *birth.parameters],
            value_type="numeric",
        )

    def _patient_resource(self) -> _Fragment:
        table_alias = self._next_alias("patient")
        predicates = [f"{table_alias}.resource_type = %s"]
        parameters: list[Any] = ["Patient"]
        if self.patient_id is not None:
            predicates.append(f"{table_alias}.resource_id = %s")
            parameters.append(self.patient_id)
        return _Fragment(
            f"(SELECT {table_alias}.resource FROM {self._resources_table} AS {table_alias} "
            f"WHERE {' AND '.join(predicates)} LIMIT 1)",
            parameters,
            value_type="jsonb",
        )

    def _patient_birth_date(self) -> _Fragment:
        patient = self._patient_resource()
        return _Fragment(
            f"NULLIF(({patient.sql}) ->> 'birthDate', '')::date",
            patient.parameters,
            value_type="date",
        )

    def _jsonb_period_range(self, fragment: _Fragment) -> _Fragment:
        return _Fragment(
            "tstzrange("
            f"NULLIF(({fragment.sql}) ->> 'start', '')::timestamptz, "
            f"NULLIF(({fragment.sql}) ->> 'end', '')::timestamptz, '[]')",
            [*fragment.parameters, *fragment.parameters],
            value_type="range",
        )

    def _scalar_text(self, fragment: _Fragment) -> tuple[str, list[Any]]:
        if fragment.value_type == "jsonb":
            return f"({fragment.sql} #>> '{{}}')", fragment.parameters
        return fragment.sql, fragment.parameters

    def _operands(
        self,
        node: ElmNode,
        aliases: dict[str, _Fragment],
        *,
        expected: int | None = None,
    ) -> list[_Fragment]:
        raw = node.get("operand")
        values = raw if isinstance(raw, list) else [raw]
        operands = [self._compile_node(value, aliases) for value in values if value is not None]
        if expected is not None and len(operands) != expected:
            raise UnsupportedElmError(
                f"ELM node '{node.type}' requires {expected} operands; got {len(operands)}."
            )
        return operands

    def _value_set(self, node: ElmNode) -> tuple[str, str | None]:
        name = str(node.get("name") or "")
        definition = self.library.value_sets.get(name)
        if definition is None:
            raise UnsupportedElmError(f"Value set '{name}' is not defined in the library.")
        return str(definition.get("id") or ""), definition.get("version")

    def _code_ref(self, node: ElmNode) -> tuple[str, str | None]:
        name = str(node.get("name") or "")
        definition = self.library.codes.get(name)
        if definition is None:
            raise UnsupportedElmError(f"Code '{name}' is not defined in the library.")
        code_system = definition.get("codeSystem")
        system_name = code_system.get("name") if isinstance(code_system, dict) else None
        system_definition = self.library.code_systems.get(str(system_name)) if system_name else None
        system = str(system_definition.get("id")) if system_definition else None
        return str(definition.get("id") or ""), system


def _validated_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid PostgreSQL {label} identifier: {value!r}")
    return value


def _reverse_direction(direction: str) -> str:
    return "DESC" if direction == "ASC" else "ASC"


def _interval_unit(unit: str) -> str:
    normalized = unit.strip("'").lower().rstrip("s")
    allowed = {
        "millisecond",
        "second",
        "minute",
        "hour",
        "day",
        "week",
        "month",
        "year",
    }
    if normalized not in allowed:
        raise UnsupportedElmError(f"Quantity unit '{unit}' cannot be used as a SQL interval.")
    return normalized
