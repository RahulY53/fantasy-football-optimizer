"""Framework-independent current-team and lineup records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CurrentTeamPlayerInput:
    """One selected squad player with team-specific prices."""

    player_id: int
    purchase_price: float
    selling_price: float


@dataclass(frozen=True, slots=True)
class CurrentTeamInput:
    """Editable state required for current-team planning."""

    name: str
    bank: float
    free_transfers: int
    wildcard_available: bool
    free_hit_available: bool
    bench_boost_available: bool
    triple_captain_available: bool
    players: tuple[CurrentTeamPlayerInput, ...]


@dataclass(frozen=True, slots=True)
class CurrentTeamPlayer:
    """One persisted squad member with canonical display metadata."""

    player_id: int
    player: str
    position: str
    team: str
    purchase_price: float
    selling_price: float
    current_price: float


@dataclass(frozen=True, slots=True)
class CurrentTeam:
    """Persisted current FPL team."""

    team_id: int
    name: str
    bank: float
    free_transfers: int
    wildcard_available: bool
    free_hit_available: bool
    bench_boost_available: bool
    triple_captain_available: bool
    players: tuple[CurrentTeamPlayer, ...]


@dataclass(frozen=True, slots=True)
class PublishedSquadPlayer:
    """One player and role from a publicly published Gameweek squad."""

    player_id: int
    purchase_price: float
    selling_price: float
    pick_position: int
    is_starting: bool
    bench_order: int | None
    is_captain: bool
    is_vice_captain: bool


@dataclass(frozen=True, slots=True)
class PublishedTeamImport:
    """Validated public Team ID payload mapped to internal player identities."""

    fpl_team_id: int
    manager_name: str
    team_name: str
    overall_rank: int | None
    total_points: int
    published_gameweek: int
    squad_value: float | None
    bank: float
    refreshed_at: datetime
    data_status: str
    players: tuple[PublishedSquadPlayer, ...]
    history: tuple[dict[str, object], ...]
    transfers: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class PublishedTeamSummary:
    """Persisted public-import metadata for presentation."""

    fpl_team_id: int
    manager_name: str
    team_name: str
    overall_rank: int | None
    total_points: int
    published_gameweek: int
    squad_value: float | None
    bank: float
    refreshed_at: datetime
    data_status: str
    starting_ids: tuple[int, ...]
    bench_ids: tuple[int, ...]
    captain_id: int
    vice_captain_id: int
    transfer_count: int
    recent_history: tuple[dict[str, object], ...]
    recent_transfers: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class LineupCandidate:
    """Forecast and ownership context for one current-squad player."""

    player_id: int
    player: str
    position: str
    team: str
    opponent: str
    current_price: float
    selling_price: float
    expected_minutes: float
    next_gw_xpts: float
    next_3_xpts: float
    next_5_xpts: float
    attacking_xpts: float
    ownership: float
    risk: float


@dataclass(frozen=True, slots=True)
class LineupPlayer:
    """One player assigned to the XI or an ordered bench slot."""

    player_id: int
    player: str
    position: str
    team: str
    opponent: str
    current_price: float
    expected_minutes: float
    next_gw_xpts: float
    ownership: float
    risk: float
    role: str
    bench_order: int | None


@dataclass(frozen=True, slots=True)
class CaptainOption:
    """One explainable captaincy lens."""

    kind: str
    player_id: int
    player: str
    score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class LineupResult:
    """Optimized starting XI, captaincy, and bench order."""

    formation: str
    starters: tuple[LineupPlayer, ...]
    bench: tuple[LineupPlayer, ...]
    captain_id: int
    vice_captain_id: int
    base_xpts: float
    projected_points: float
    next_3_squad_xpts: float
    next_5_squad_xpts: float
    captain_options: tuple[CaptainOption, ...]
