"""Result types for DQM measure evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PopulationResult:
    """The resolved outcome for one population within a group."""

    population_type: str
    expression: str
    count: int
    #: For episode-of-care measures, the resource ids that qualified.
    member_ids: list[str] = field(default_factory=list)
    #: For patient-based measures, the boolean membership.
    in_population: bool | None = None


@dataclass(slots=True)
class GroupResult:
    group_id: str
    basis: str
    scoring: str
    populations: dict[str, PopulationResult] = field(default_factory=dict)
    numerator_count: int = 0
    denominator_count: int = 0
    measure_score: float | None = None

    def population(self, population_type: str) -> PopulationResult | None:
        return self.populations.get(population_type)


@dataclass(slots=True)
class MeasureResult:
    """Top-level result of evaluating a measure for one subject/bundle."""

    measure_url: str | None
    measure_name: str | None
    subject_id: str | None
    groups: list[GroupResult] = field(default_factory=list)
    supplemental_data: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def primary_group(self) -> GroupResult | None:
        return self.groups[0] if self.groups else None
