"""Confidence-scored vendor-to-FPL fixture matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fpl_optimizer.odds.aliases import TeamAliases


@dataclass(frozen=True, slots=True)
class FplFixtureIdentity:
    """Minimal local fixture identity used during matching."""

    fpl_id: int
    home: str
    away: str
    kickoff_at: datetime


@dataclass(frozen=True, slots=True)
class VendorEvent:
    """Minimal vendor event identity."""

    event_id: int
    home: str
    away: str
    kickoff_at: datetime
    league: str


@dataclass(frozen=True, slots=True)
class FixtureMatch:
    """Accepted fixture link with an auditable confidence score."""

    event_id: int
    fixture_fpl_id: int
    confidence: float
    kickoff_difference_minutes: float


def match_fixture(
    event: VendorEvent,
    fixtures: list[FplFixtureIdentity],
    aliases: TeamAliases,
    minimum_confidence: float = 85.0,
) -> FixtureMatch | None:
    """Match both teams and kickoff; reject low-confidence or ambiguous candidates."""

    candidates: list[FixtureMatch] = []
    for fixture in fixtures:
        teams_match = (
            aliases.canonical(event.home) == aliases.canonical(fixture.home)
            and aliases.canonical(event.away) == aliases.canonical(fixture.away)
        )
        if not teams_match:
            continue
        difference = abs((event.kickoff_at - fixture.kickoff_at).total_seconds()) / 60
        time_score = max(0.0, 25.0 * (1 - difference / 180))
        league_score = 5.0 if "premier" in event.league.lower() else 0.0
        confidence = 70.0 + time_score + league_score
        if confidence >= minimum_confidence:
            candidates.append(
                FixtureMatch(event.event_id, fixture.fpl_id, confidence, difference)
            )
    candidates.sort(key=lambda item: (-item.confidence, item.kickoff_difference_minutes))
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[0].confidence == candidates[1].confidence:
        return None
    return candidates[0]
