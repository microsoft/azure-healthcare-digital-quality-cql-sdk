"""Proportion-measure scoring for patient-based and episode-of-care eCQMs.

Given a parsed :class:`~cql_sdk.dqm.measure.Measure`, an
:class:`~cql_sdk.invocation.toolkit.InvocationToolkit` with the measure's
libraries registered, and a runtime context bound to a subject's data, this
module evaluates each rate group's population criteria and resolves the
standard proportion relationships:

    denominator ⊆ initial population
    numerator   ⊆ (denominator minus denominator exclusions)

For ``boolean`` (patient) basis the populations collapse to membership flags;
for an episode basis (e.g. ``Encounter``) they are sets of qualifying
resources resolved by id.
"""

from __future__ import annotations

from typing import Any

from cql_sdk.dqm import measure as M
from cql_sdk.dqm.results import GroupResult, MeasureResult, PopulationResult
from cql_sdk.invocation.toolkit import InvocationToolkit
from cql_sdk.runtime.context import RuntimeContext


def evaluate_measure(
    measure: M.Measure,
    toolkit: InvocationToolkit,
    primary_library: str,
    context: RuntimeContext,
    *,
    parameters: dict[str, Any] | None = None,
) -> MeasureResult:
    """Evaluate ``measure`` for a single subject/bundle and return a result."""
    subject_id = _resource_id(context.subject) if isinstance(context.subject, dict) else None
    result = MeasureResult(
        measure_url=measure.url,
        measure_name=measure.name,
        subject_id=subject_id,
    )

    for group in measure.groups:
        raw: dict[str, Any] = {}
        for pop in group.populations:
            try:
                raw[pop.population_type] = toolkit.invoke(
                    library_identifier=primary_library,
                    definition=pop.expression,
                    parameters=parameters,
                    context=context,
                )
            except Exception as exc:  # pylint: disable=broad-except
                result.errors[f"{group.group_id}:{pop.population_type}"] = (
                    f"{type(exc).__name__}: {exc}"
                )
                raw[pop.population_type] = None
        if group.is_episode_of_care:
            result.groups.append(_score_episode(group, raw))
        else:
            result.groups.append(_score_boolean(group, raw))

    for sde in measure.supplemental_data:
        try:
            value = toolkit.invoke(
                library_identifier=primary_library,
                definition=sde.expression,
                parameters=parameters,
                context=context,
            )
            result.supplemental_data[sde.expression] = _describe(value)
        except Exception as exc:  # pylint: disable=broad-except
            result.errors[f"sde:{sde.expression}"] = f"{type(exc).__name__}: {exc}"

    return result


# --- boolean (patient) basis ----------------------------------------------


def _score_boolean(group: M.MeasureGroup, raw: dict[str, Any]) -> GroupResult:
    ip = _truthy(raw.get(M.INITIAL_POPULATION))
    denom = _truthy(raw.get(M.DENOMINATOR)) and ip if M.DENOMINATOR in raw else ip
    den_excl = _truthy(raw.get(M.DENOMINATOR_EXCLUSION)) and denom
    numerator = _truthy(raw.get(M.NUMERATOR)) and denom and not den_excl
    num_excl = _truthy(raw.get(M.NUMERATOR_EXCLUSION)) and numerator
    numerator = numerator and not num_excl
    den_excep = (
        _truthy(raw.get(M.DENOMINATOR_EXCEPTION))
        and denom
        and not den_excl
        and not numerator
    )

    perf_denom = 1 if (denom and not den_excl and not den_excep) else 0
    perf_num = 1 if numerator else 0

    resolved = {
        M.INITIAL_POPULATION: ip,
        M.DENOMINATOR: denom,
        M.DENOMINATOR_EXCLUSION: den_excl,
        M.DENOMINATOR_EXCEPTION: den_excep,
        M.NUMERATOR: numerator,
        M.NUMERATOR_EXCLUSION: num_excl,
    }
    populations: dict[str, PopulationResult] = {}
    for pop in group.populations:
        flag = bool(resolved.get(pop.population_type, _truthy(raw.get(pop.population_type))))
        populations[pop.population_type] = PopulationResult(
            population_type=pop.population_type,
            expression=pop.expression,
            count=1 if flag else 0,
            in_population=flag,
        )

    score = (perf_num / perf_denom) if perf_denom > 0 else None
    return GroupResult(
        group_id=group.group_id,
        basis=group.basis,
        scoring=group.scoring,
        populations=populations,
        numerator_count=perf_num,
        denominator_count=perf_denom,
        measure_score=score,
    )


# --- episode-of-care basis ------------------------------------------------


def _score_episode(group: M.MeasureGroup, raw: dict[str, Any]) -> GroupResult:
    id_sets = {ptype: _as_id_map(value) for ptype, value in raw.items()}

    def ids(ptype: str) -> set[str]:
        return set(id_sets.get(ptype, {}).keys())

    ip = ids(M.INITIAL_POPULATION)
    denom = (ids(M.DENOMINATOR) & ip) if M.DENOMINATOR in raw else ip
    den_excl = ids(M.DENOMINATOR_EXCLUSION) & denom
    eligible = denom - den_excl
    numerator = ids(M.NUMERATOR) & eligible
    num_excl = ids(M.NUMERATOR_EXCLUSION) & numerator
    numerator = numerator - num_excl
    den_excep = (ids(M.DENOMINATOR_EXCEPTION) & eligible) - numerator
    perf_denom = eligible - den_excep

    resolved = {
        M.INITIAL_POPULATION: ip,
        M.DENOMINATOR: denom,
        M.DENOMINATOR_EXCLUSION: den_excl,
        M.DENOMINATOR_EXCEPTION: den_excep,
        M.NUMERATOR: numerator,
        M.NUMERATOR_EXCLUSION: num_excl,
    }
    populations: dict[str, PopulationResult] = {}
    for pop in group.populations:
        member = sorted(resolved.get(pop.population_type, ids(pop.population_type)))
        populations[pop.population_type] = PopulationResult(
            population_type=pop.population_type,
            expression=pop.expression,
            count=len(member),
            member_ids=member,
        )

    numerator_count = len(numerator)
    denominator_count = len(perf_denom)
    score = (numerator_count / denominator_count) if denominator_count > 0 else None
    return GroupResult(
        group_id=group.group_id,
        basis=group.basis,
        scoring=group.scoring,
        populations=populations,
        numerator_count=numerator_count,
        denominator_count=denominator_count,
        measure_score=score,
    )


# --- helpers --------------------------------------------------------------


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set)):
        return any(v is not None for v in value)
    return bool(value)


def _as_id_map(value: Any) -> dict[str, Any]:
    """Map a population value (list of resources) to {id: resource}."""
    out: dict[str, Any] = {}
    if value is None:
        return out
    items = value if isinstance(value, list) else [value]
    for item in items:
        if item is None:
            continue
        out[_resource_id(item)] = item
    return out


def _resource_id(resource: Any) -> str:
    if isinstance(resource, dict):
        rid = resource.get("id")
        if isinstance(rid, str) and rid:
            rtype = resource.get("resourceType")
            return f"{rtype}/{rid}" if rtype else rid
    return f"__obj_{id(resource)}"


def _describe(value: Any) -> Any:
    if isinstance(value, (list, tuple, set)):
        return {"kind": "list", "count": sum(1 for v in value if v is not None)}
    if isinstance(value, bool) or value is None:
        return value
    return str(value)
