"""Phase 1 relational entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fpl_optimizer.database.base import Base


class DataSnapshot(Base):
    """Metadata for an immutable raw provider payload."""

    __tablename__ = "data_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    endpoint: Mapped[str] = mapped_column(String(200))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    cache_path: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(30), default="fpl-v1")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)


class Gameweek(Base):
    """An official FPL event."""

    __tablename__ = "gameweek"

    id: Mapped[int] = mapped_column(primary_key=True)
    fpl_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    is_next: Mapped[bool] = mapped_column(Boolean, default=False)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("data_snapshot.id"))


class Team(Base):
    """A Premier League team."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(primary_key=True)
    fpl_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(10))
    strength: Mapped[int] = mapped_column(Integer)
    strength_attack_home: Mapped[int] = mapped_column(Integer)
    strength_attack_away: Mapped[int] = mapped_column(Integer)
    strength_defence_home: Mapped[int] = mapped_column(Integer)
    strength_defence_away: Mapped[int] = mapped_column(Integer)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("data_snapshot.id"))


class Player(Base):
    """Stable identity and current status for an FPL player."""

    __tablename__ = "player"

    id: Mapped[int] = mapped_column(primary_key=True)
    fpl_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    position: Mapped[str] = mapped_column(String(3), index=True)
    web_name: Mapped[str] = mapped_column(String(100), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    second_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(220), default="", index=True)
    display_name: Mapped[str] = mapped_column(String(220), default="", index=True)
    status: Mapped[str] = mapped_column(String(10), index=True)
    news: Mapped[str] = mapped_column(Text, default="")
    chance_next_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("data_snapshot.id"))

    team: Mapped[Team] = relationship()
    snapshots: Mapped[list[PlayerSnapshot]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


class PlayerWatchlist(Base):
    """Persistent user interest in one canonical FPL player."""

    __tablename__ = "player_watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("player.id", ondelete="CASCADE"), unique=True, index=True
    )
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    player: Mapped[Player] = relationship()


class PlayerAvailabilitySnapshot(Base):
    """Timestamped FPL availability and news for change detection."""

    __tablename__ = "player_availability_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "data_snapshot_id", name="uq_player_availability_data_snapshot"
        ),
        Index(
            "ix_player_availability_player_observed", "player_id", "observed_at"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("player.id", ondelete="CASCADE"), index=True
    )
    data_snapshot_id: Mapped[int] = mapped_column(ForeignKey("data_snapshot.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(10))
    news: Mapped[str] = mapped_column(Text, default="")
    chance_next_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    player: Mapped[Player] = relationship()


class PlayerSnapshot(Base):
    """Timestamped current-season player metrics."""

    __tablename__ = "player_snapshot"
    __table_args__ = (
        UniqueConstraint("player_id", "data_snapshot_id", name="uq_player_data_snapshot"),
        Index("ix_player_snapshot_player_observed", "player_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    data_snapshot_id: Mapped[int] = mapped_column(ForeignKey("data_snapshot.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price_tenths: Mapped[int] = mapped_column(Integer)
    total_points: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int] = mapped_column(Integer)
    starts: Mapped[int] = mapped_column(Integer)
    goals: Mapped[int] = mapped_column(Integer)
    assists: Mapped[int] = mapped_column(Integer)
    clean_sheets: Mapped[int] = mapped_column(Integer)
    saves: Mapped[int] = mapped_column(Integer)
    bonus: Mapped[int] = mapped_column(Integer)
    bps: Mapped[int] = mapped_column(Integer)
    selected_pct: Mapped[float] = mapped_column(Float)
    transfers_in: Mapped[int] = mapped_column(Integer)
    transfers_out: Mapped[int] = mapped_column(Integer)
    form: Mapped[float] = mapped_column(Float)
    points_per_game: Mapped[float] = mapped_column(Float)
    ict_index: Mapped[float] = mapped_column(Float)
    own_goals: Mapped[int] = mapped_column(Integer, default=0)
    penalties_saved: Mapped[int] = mapped_column(Integer, default=0)
    penalties_missed: Mapped[int] = mapped_column(Integer, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, default=0)
    clearances_blocks_interceptions: Mapped[int] = mapped_column(Integer, default=0)
    tackles: Mapped[int] = mapped_column(Integer, default=0)
    recoveries: Mapped[int] = mapped_column(Integer, default=0)
    defensive_contribution: Mapped[int] = mapped_column(Integer, default=0)

    player: Mapped[Player] = relationship(back_populates="snapshots")


class Fixture(Base):
    """A current or historical Premier League fixture."""

    __tablename__ = "fixture"
    __table_args__ = (Index("ix_fixture_gameweek_kickoff", "gameweek_id", "kickoff_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fpl_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    gameweek_id: Mapped[int | None] = mapped_column(
        ForeignKey("gameweek.id"), nullable=True, index=True
    )
    home_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    home_difficulty: Mapped[int] = mapped_column(Integer)
    away_difficulty: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("data_snapshot.id"))

    gameweek: Mapped[Gameweek | None] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])


class ModelVersion(Base):
    """Immutable metadata describing a reproducible forecast model."""

    __tablename__ = "model_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    semantic_version: Mapped[str] = mapped_column(String(30))
    feature_schema: Mapped[str] = mapped_column(String(50))
    parameter_json: Mapped[str] = mapped_column(Text)
    training_cutoff_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    code_revision: Mapped[str] = mapped_column(String(80), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (UniqueConstraint("name", "semantic_version", name="uq_model_name_version"),)


class PlayerForecast(Base):
    """A timestamped player projection aggregated to one FPL Gameweek."""

    __tablename__ = "player_forecast"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "gameweek_id",
            "model_version_id",
            "prediction_at",
            name="uq_player_gameweek_model_prediction",
        ),
        Index(
            "ix_forecast_player_gameweek_prediction", "player_id", "gameweek_id", "prediction_at"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    gameweek_id: Mapped[int] = mapped_column(ForeignKey("gameweek.id"), index=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_version.id"))
    prediction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expected_minutes: Mapped[float] = mapped_column(Float)
    appearance_xpts: Mapped[float] = mapped_column(Float)
    goal_xpts: Mapped[float] = mapped_column(Float)
    assist_xpts: Mapped[float] = mapped_column(Float)
    clean_sheet_xpts: Mapped[float] = mapped_column(Float)
    save_xpts: Mapped[float] = mapped_column(Float)
    bonus_xpts: Mapped[float] = mapped_column(Float)
    deduction_xpts: Mapped[float] = mapped_column(Float)
    defensive_contribution_xpts: Mapped[float] = mapped_column(Float, default=0.0)
    stat_xpts: Mapped[float] = mapped_column(Float)
    fixture_count: Mapped[int] = mapped_column(Integer)
    opponent_summary: Mapped[str] = mapped_column(String(200), default="Blank")
    confidence: Mapped[str] = mapped_column(String(10), default="Low")
    component_json: Mapped[str] = mapped_column(Text)

    player: Mapped[Player] = relationship()
    gameweek: Mapped[Gameweek] = relationship()
    model_version: Mapped[ModelVersion] = relationship()


class OddsSnapshot(Base):
    """One imported timestamped bookmaker price."""

    __tablename__ = "odds_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "provider",
            "bookmaker",
            "market",
            "selection",
            "observed_at",
            name="uq_odds_observation",
        ),
        Index("ix_odds_fixture_market_observed", "fixture_id", "market", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixture.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    bookmaker: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(40), index=True)
    selection: Mapped[str] = mapped_column(String(20))
    decimal_odds: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snapshot_kind: Mapped[str] = mapped_column(String(20), default="current")
    source_ref: Mapped[str] = mapped_column(Text, default="")

    fixture: Mapped[Fixture] = relationship()


class GoalscorerOddsSnapshot(Base):
    """One player-linked anytime-goalscorer price."""

    __tablename__ = "goalscorer_odds_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "player_id",
            "provider",
            "bookmaker",
            "observed_at",
            name="uq_goalscorer_odds_observation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixture.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    bookmaker: Mapped[str] = mapped_column(String(100))
    decimal_odds: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snapshot_kind: Mapped[str] = mapped_column(String(20), default="current")
    source_ref: Mapped[str] = mapped_column(Text, default="")

    fixture: Mapped[Fixture] = relationship()
    player: Mapped[Player] = relationship()


class MarketForecast(Base):
    """Market-derived probabilities and expected goals for one fixture."""

    __tablename__ = "market_forecast"
    __table_args__ = (
        UniqueConstraint("fixture_id", "prediction_at", name="uq_market_fixture_prediction"),
        Index("ix_market_fixture_prediction", "fixture_id", "prediction_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixture.id"), index=True)
    prediction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    devig_method: Mapped[str] = mapped_column(String(30))
    home_win: Mapped[float] = mapped_column(Float)
    draw: Mapped[float] = mapped_column(Float)
    away_win: Mapped[float] = mapped_column(Float)
    over_2_5: Mapped[float] = mapped_column(Float)
    btts_yes: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_over_1_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_over_1_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_xg: Mapped[float] = mapped_column(Float)
    away_xg: Mapped[float] = mapped_column(Float)
    home_clean_sheet: Mapped[float] = mapped_column(Float)
    away_clean_sheet: Mapped[float] = mapped_column(Float)
    dispersion: Mapped[float] = mapped_column(Float)
    bookmaker_count: Mapped[int] = mapped_column(Integer)
    fit_residual: Mapped[float] = mapped_column(Float)
    fit_success: Mapped[bool] = mapped_column(Boolean)
    advanced_market_count: Mapped[int] = mapped_column(Integer, default=0)

    fixture: Mapped[Fixture] = relationship()


class PlayerMarketForecast(Base):
    """Independent market-derived player projection for one Gameweek."""

    __tablename__ = "player_market_forecast"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "gameweek_id",
            "prediction_at",
            name="uq_player_market_gameweek_prediction",
        ),
        Index(
            "ix_player_market_gameweek_prediction",
            "player_id",
            "gameweek_id",
            "prediction_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    gameweek_id: Mapped[int] = mapped_column(ForeignKey("gameweek.id"), index=True)
    prediction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    appearance_xpts: Mapped[float] = mapped_column(Float)
    goal_xpts: Mapped[float] = mapped_column(Float)
    assist_xpts: Mapped[float] = mapped_column(Float)
    clean_sheet_xpts: Mapped[float] = mapped_column(Float)
    save_xpts: Mapped[float] = mapped_column(Float)
    bonus_xpts: Mapped[float] = mapped_column(Float)
    deduction_xpts: Mapped[float] = mapped_column(Float)
    defensive_contribution_xpts: Mapped[float] = mapped_column(Float, default=0.0)
    market_xpts: Mapped[float] = mapped_column(Float)
    fixture_count: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(10))
    component_json: Mapped[str] = mapped_column(Text)
    goalscorer_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    player: Mapped[Player] = relationship()
    gameweek: Mapped[Gameweek] = relationship()


class Strategy(Base):
    """A locally saved user decision profile."""

    __tablename__ = "strategy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20))
    preset_name: Mapped[str] = mapped_column(String(100))
    horizon: Mapped[int] = mapped_column(Integer)
    risk_appetite: Mapped[int] = mapped_column(Integer)
    transfer_reluctance: Mapped[int] = mapped_column(Integer)
    ownership_preference: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    weights: Mapped[list[StrategyWeight]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan"
    )


class StrategyWeight(Base):
    """One raw, user-controlled feature weight."""

    __tablename__ = "strategy_weight"
    __table_args__ = (
        UniqueConstraint("strategy_id", "feature", name="uq_strategy_feature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategy.id"), index=True)
    feature: Mapped[str] = mapped_column(String(50))
    raw_weight: Mapped[int] = mapped_column(Integer)

    strategy: Mapped[Strategy] = relationship(back_populates="weights")


class OptimizationRun(Base):
    """Immutable input and output record for one squad solve."""

    __tablename__ = "optimization_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    optimizer_type: Mapped[str] = mapped_column(String(40), index=True)
    solver: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), index=True)
    budget: Mapped[float] = mapped_column(Float)
    total_cost: Mapped[float] = mapped_column(Float)
    objective_score: Mapped[float] = mapped_column(Float)
    total_xpts: Mapped[float] = mapped_column(Float)
    market_weight: Mapped[float] = mapped_column(Float)
    strategy_json: Mapped[str] = mapped_column(Text)
    constraints_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)


class UserTeam(Base):
    """One locally managed current FPL team."""

    __tablename__ = "user_team"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    bank_tenths: Mapped[int] = mapped_column(Integer)
    free_transfers: Mapped[int] = mapped_column(Integer)
    wildcard_available: Mapped[bool] = mapped_column(Boolean, default=True)
    free_hit_available: Mapped[bool] = mapped_column(Boolean, default=True)
    bench_boost_available: Mapped[bool] = mapped_column(Boolean, default=True)
    triple_captain_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fpl_team_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    manager_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    overall_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_gameweek: Mapped[int | None] = mapped_column(Integer, nullable=True)
    squad_value_tenths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfers_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    players: Mapped[list[UserPlayer]] = relationship(
        back_populates="user_team", cascade="all, delete-orphan"
    )


class UserPlayer(Base):
    """Current-team membership and team-specific price state."""

    __tablename__ = "user_player"
    __table_args__ = (
        UniqueConstraint("user_team_id", "player_id", name="uq_user_team_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_team_id: Mapped[int] = mapped_column(ForeignKey("user_team.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    purchase_price_tenths: Mapped[int] = mapped_column(Integer)
    selling_price_tenths: Mapped[int] = mapped_column(Integer)
    imported_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_starting: Mapped[bool] = mapped_column(Boolean, default=False)
    bench_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vice_captain: Mapped[bool] = mapped_column(Boolean, default=False)

    user_team: Mapped[UserTeam] = relationship(back_populates="players")
    player: Mapped[Player] = relationship()


class LineupRun(Base):
    """One reproducible lineup and captaincy decision."""

    __tablename__ = "lineup_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_team_id: Mapped[int] = mapped_column(ForeignKey("user_team.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    market_weight: Mapped[float] = mapped_column(Float)
    formation: Mapped[str] = mapped_column(String(10))
    projected_points: Mapped[float] = mapped_column(Float)
    strategy_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)

    user_team: Mapped[UserTeam] = relationship()


class TransferPlan(Base):
    """One reproducible roll/transfer comparison run."""

    __tablename__ = "transfer_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_team_id: Mapped[int] = mapped_column(ForeignKey("user_team.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    horizon: Mapped[int] = mapped_column(Integer)
    market_weight: Mapped[float] = mapped_column(Float)
    free_transfers: Mapped[int] = mapped_column(Integer)
    bank: Mapped[float] = mapped_column(Float)
    transfer_reluctance: Mapped[int] = mapped_column(Integer)
    recommendation: Mapped[str] = mapped_column(String(40), index=True)
    strategy_json: Mapped[str] = mapped_column(Text)
    evaluation_json: Mapped[str] = mapped_column(Text)

    user_team: Mapped[UserTeam] = relationship()


class PlannerRun(Base):
    """One reproducible multi-Gameweek planning run."""

    __tablename__ = "planner_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_team_id: Mapped[int] = mapped_column(ForeignKey("user_team.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    horizon: Mapped[int] = mapped_column(Integer)
    market_weight: Mapped[float] = mapped_column(Float)
    starting_free_transfers: Mapped[int] = mapped_column(Integer)
    starting_bank: Mapped[float] = mapped_column(Float)
    total_transfers: Mapped[int] = mapped_column(Integer)
    total_hits: Mapped[int] = mapped_column(Integer)
    net_projected_points: Mapped[float] = mapped_column(Float)
    strategy_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)

    user_team: Mapped[UserTeam] = relationship()


class SimulationRun(Base):
    """One reproducible Monte Carlo run for the current team."""

    __tablename__ = "simulation_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_team_id: Mapped[int] = mapped_column(ForeignKey("user_team.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    horizon: Mapped[int] = mapped_column(Integer)
    iterations: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    market_weight: Mapped[float] = mapped_column(Float)
    mean_points: Mapped[float] = mapped_column(Float)
    median_points: Mapped[float] = mapped_column(Float)
    p10_points: Mapped[float] = mapped_column(Float)
    p90_points: Mapped[float] = mapped_column(Float)
    result_json: Mapped[str] = mapped_column(Text)

    user_team: Mapped[UserTeam] = relationship()


class ChipRun(Base):
    """One reproducible four-chip opportunity evaluation."""

    __tablename__ = "chip_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_team_id: Mapped[int] = mapped_column(ForeignKey("user_team.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    horizon: Mapped[int] = mapped_column(Integer)
    market_weight: Mapped[float] = mapped_column(Float)
    budget: Mapped[float] = mapped_column(Float)
    best_chip: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    best_gain: Mapped[float] = mapped_column(Float)
    strategy_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)

    user_team: Mapped[UserTeam] = relationship()


class PlayerGameweekActual(Base):
    """Final historical FPL outcome for one player and Gameweek."""

    __tablename__ = "player_gameweek_actual"
    __table_args__ = (
        UniqueConstraint("player_id", "gameweek_id", name="uq_player_gameweek_actual"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), index=True)
    gameweek_id: Mapped[int] = mapped_column(ForeignKey("gameweek.id"), index=True)
    actual_points: Mapped[float] = mapped_column(Float)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clean_sheets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_ref: Mapped[str] = mapped_column(Text, default="")

    player: Mapped[Player] = relationship()
    gameweek: Mapped[Gameweek] = relationship()


class BacktestRun(Base):
    """Immutable historical calibration and holdout evaluation."""

    __tablename__ = "backtest_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observation_count: Mapped[int] = mapped_column(Integer)
    gameweek_count: Mapped[int] = mapped_column(Integer)
    evaluation_mode: Mapped[str] = mapped_column(String(40))
    selected_market_weight: Mapped[float] = mapped_column(Float)
    statistical_rmse: Mapped[float] = mapped_column(Float)
    selected_blend_rmse: Mapped[float] = mapped_column(Float)
    result_json: Mapped[str] = mapped_column(Text)
