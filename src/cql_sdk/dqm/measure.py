"""A minimal FHIR ``Measure`` resource model for DQM evaluation.

Parses the parts of a FHIR R4 ``Measure`` resource that drive electronic
clinical quality measure (eCQM) scoring: the population criteria per rate
group, the population basis (``boolean`` for patient-based measures or a
resource type such as ``Encounter`` for episode-of-care measures), the scoring
method, improvement notation, and supplemental data elements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Canonical FHIR population-type codes (http://terminology.hl7.org/CodeSystem/measure-population)
INITIAL_POPULATION = "initial-population"
DENOMINATOR = "denominator"
DENOMINATOR_EXCLUSION = "denominator-exclusion"
DENOMINATOR_EXCEPTION = "denominator-exception"
NUMERATOR = "numerator"
NUMERATOR_EXCLUSION = "numerator-exclusion"
MEASURE_POPULATION = "measure-population"
MEASURE_OBSERVATION = "measure-observation"

_POPULATION_BASIS_EXT = (
    "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-populationBasis"
)


@dataclass(slots=True)
class MeasurePopulation:
    """A single population criterion within a group."""

    population_type: str
    expression: str
    population_id: str | None = None


@dataclass(slots=True)
class MeasureGroup:
    """A single rate/group within a measure."""

    group_id: str
    populations: list[MeasurePopulation] = field(default_factory=list)
    basis: str = "boolean"
    scoring: str = "proportion"
    improvement_notation: str = "increase"

    def population(self, population_type: str) -> MeasurePopulation | None:
        for pop in self.populations:
            if pop.population_type == population_type:
                return pop
        return None

    @property
    def is_episode_of_care(self) -> bool:
        return self.basis not in ("boolean", "Boolean", "", None)


@dataclass(slots=True)
class SupplementalDataElement:
    expression: str
    sde_id: str | None = None
    usage: str = "supplemental-data"


@dataclass(slots=True)
class Measure:
    """Parsed FHIR ``Measure`` resource."""

    url: str | None
    name: str | None
    version: str | None
    library: list[str] = field(default_factory=list)
    scoring: str = "proportion"
    improvement_notation: str = "increase"
    basis: str = "boolean"
    groups: list[MeasureGroup] = field(default_factory=list)
    supplemental_data: list[SupplementalDataElement] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_library_name(self) -> str | None:
        """Return the bare library name from the first ``library`` canonical."""
        if not self.library:
            return None
        canonical = self.library[0]
        tail = canonical.rsplit("/", 1)[-1]
        return tail.split("|", 1)[0]

    @classmethod
    def from_resource(cls, resource: dict[str, Any]) -> Measure:
        if resource.get("resourceType") != "Measure":
            raise ValueError("Resource is not a FHIR Measure")

        scoring = _coding_code(resource.get("scoring")) or "proportion"
        improvement = _coding_code(resource.get("improvementNotation")) or "increase"
        default_basis = _extension_value_code(resource.get("extension"), _POPULATION_BASIS_EXT) or (
            _value_code(resource.get("basis")) or "boolean"
        )

        library = [str(x) for x in (resource.get("library") or []) if isinstance(x, str)]

        groups: list[MeasureGroup] = []
        for idx, g in enumerate(resource.get("group") or []):
            if not isinstance(g, dict):
                continue
            group_basis = (
                _extension_value_code(g.get("extension"), _POPULATION_BASIS_EXT) or default_basis
            )
            group_scoring = _coding_code(g.get("scoring")) or scoring
            group_improvement = _coding_code(g.get("improvementNotation")) or improvement
            populations: list[MeasurePopulation] = []
            for p in g.get("population") or []:
                if not isinstance(p, dict):
                    continue
                ptype = _coding_code(p.get("code"))
                expression = _criteria_expression(p.get("criteria"))
                if ptype and expression:
                    populations.append(
                        MeasurePopulation(
                            population_type=ptype,
                            expression=expression,
                            population_id=p.get("id"),
                        )
                    )
            groups.append(
                MeasureGroup(
                    group_id=str(g.get("id") or f"Group_{idx + 1}"),
                    populations=populations,
                    basis=group_basis,
                    scoring=group_scoring,
                    improvement_notation=group_improvement,
                )
            )

        sdes: list[SupplementalDataElement] = []
        for s in resource.get("supplementalData") or []:
            if not isinstance(s, dict):
                continue
            expression = _criteria_expression(s.get("criteria"))
            if expression:
                sdes.append(
                    SupplementalDataElement(
                        expression=expression,
                        sde_id=s.get("id"),
                        usage=_coding_code(_first(s.get("usage"))) or "supplemental-data",
                    )
                )

        return cls(
            url=resource.get("url"),
            name=resource.get("name"),
            version=resource.get("version"),
            library=library,
            scoring=scoring,
            improvement_notation=improvement,
            basis=default_basis,
            groups=groups,
            supplemental_data=sdes,
            raw=resource,
        )


# --- parsing helpers ------------------------------------------------------


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _coding_code(codeable: Any) -> str | None:
    """Return the first coding code from a CodeableConcept (or plain dict)."""
    if not isinstance(codeable, dict):
        return None
    coding = codeable.get("coding")
    if isinstance(coding, list):
        for c in coding:
            if isinstance(c, dict):
                code = c.get("code")
                if isinstance(code, str):
                    return code
    code = codeable.get("code")
    if isinstance(code, str):
        return code
    return None


def _value_code(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return _coding_code(value)


def _criteria_expression(criteria: Any) -> str | None:
    if isinstance(criteria, dict):
        expression = criteria.get("expression")
        if isinstance(expression, str):
            return expression
    if isinstance(criteria, str):
        return criteria
    return None


def _extension_value_code(extensions: Any, url: str) -> str | None:
    if not isinstance(extensions, list):
        return None
    for ext in extensions:
        if isinstance(ext, dict) and ext.get("url") == url:
            value_code = ext.get("valueCode")
            if isinstance(value_code, str):
                return value_code
            value_string = ext.get("valueString")
            if isinstance(value_string, str):
                return value_string
    return None
