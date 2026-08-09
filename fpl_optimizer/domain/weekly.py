"""Framework-independent weekly decision summary records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceFactor:
    """One transparent contributor to recommendation confidence."""

    label: str
    score: float
    explanation: str


@dataclass(frozen=True, slots=True)
class WeeklyDecisionSummary:
    """Concise decision card assembled from existing optimizer outputs."""

    action: str
    action_kind: str
    rationale: str
    alternative: str
    alternative_gain: float
    projected_score: float
    confidence_score: float
    confidence_label: str
    risk_score: float
    risk_label: str
    recommended_transfers: int
    hit_cost: int
    captain: str
    vice_captain: str
    formation: str
    next_3_squad_xpts: float
    next_5_squad_xpts: float
    first_gameweek: str | None
    confidence_factors: tuple[ConfidenceFactor, ...]

