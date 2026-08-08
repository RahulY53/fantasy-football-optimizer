"""Persistence for imported odds and market-derived forecasts."""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from fpl_optimizer.database.models import (
    Fixture,
    Gameweek,
    GoalscorerOddsSnapshot,
    MarketForecast,
    OddsSnapshot,
    Player,
    PlayerMarketForecast,
    Team,
)
from fpl_optimizer.domain.enums import OddsMarket, OddsSelection, OddsSnapshotKind
from fpl_optimizer.domain.markets import (
    GoalscorerOddsQuote,
    MarketFixtureOutput,
    OddsQuote,
    PlayerMarketOutput,
)


class OddsRepository:
    """Store odds snapshots and their independent forecast outputs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def import_quotes(self, quotes: list[OddsQuote], imported_at: datetime) -> int:
        """Insert valid new observations idempotently and return the inserted count."""

        fixture_ids = dict(self.session.execute(select(Fixture.fpl_id, Fixture.id)).tuples().all())
        inserted = 0
        for quote in quotes:
            fixture_id = fixture_ids.get(quote.fixture_fpl_id)
            if fixture_id is None:
                raise ValueError(f"Unknown FPL fixture ID: {quote.fixture_fpl_id}")
            existing = self.session.scalar(
                select(OddsSnapshot.id).where(
                    OddsSnapshot.fixture_id == fixture_id,
                    OddsSnapshot.provider == quote.provider,
                    OddsSnapshot.bookmaker == quote.bookmaker,
                    OddsSnapshot.market == quote.market.value,
                    OddsSnapshot.selection == quote.selection.value,
                    OddsSnapshot.observed_at == quote.observed_at,
                )
            )
            if existing is not None:
                continue
            self.session.add(
                OddsSnapshot(
                    fixture_id=fixture_id,
                    provider=quote.provider,
                    bookmaker=quote.bookmaker,
                    market=quote.market.value,
                    selection=quote.selection.value,
                    decimal_odds=quote.decimal_odds,
                    observed_at=quote.observed_at,
                    imported_at=imported_at,
                    snapshot_kind=quote.snapshot_kind.value,
                    source_ref=quote.source_ref,
                )
            )
            inserted += 1
        return inserted

    def fixture_quotes(self) -> dict[int, list[OddsQuote]]:
        """Return all stored quotes grouped by database fixture ID."""

        statement = select(OddsSnapshot, Fixture.fpl_id).join(
            Fixture, OddsSnapshot.fixture_id == Fixture.id
        )
        grouped: dict[int, list[OddsQuote]] = {}
        for row, fixture_fpl_id in self.session.execute(statement):
            grouped.setdefault(row.fixture_id, []).append(
                OddsQuote(
                    fixture_fpl_id=fixture_fpl_id,
                    provider=row.provider,
                    bookmaker=row.bookmaker,
                    market=OddsMarket(row.market),
                    selection=OddsSelection(row.selection),
                    decimal_odds=row.decimal_odds,
                    observed_at=_utc(row.observed_at),
                    snapshot_kind=OddsSnapshotKind(row.snapshot_kind),
                    source_ref=row.source_ref,
                )
            )
        return grouped

    def import_goalscorer_quotes(
        self, quotes: list[GoalscorerOddsQuote], imported_at: datetime
    ) -> int:
        """Insert player-linked goalscorer prices idempotently."""

        fixture_ids = dict(
            self.session.execute(select(Fixture.fpl_id, Fixture.id)).tuples().all()
        )
        player_ids = dict(
            self.session.execute(select(Player.fpl_id, Player.id)).tuples().all()
        )
        inserted = 0
        for quote in quotes:
            fixture_id = fixture_ids.get(quote.fixture_fpl_id)
            if fixture_id is None:
                raise ValueError(f"Unknown FPL fixture ID: {quote.fixture_fpl_id}")
            player_id = player_ids.get(quote.player_fpl_id)
            if player_id is None:
                raise ValueError(f"Unknown FPL player ID: {quote.player_fpl_id}")
            existing = self.session.scalar(
                select(GoalscorerOddsSnapshot.id).where(
                    GoalscorerOddsSnapshot.fixture_id == fixture_id,
                    GoalscorerOddsSnapshot.player_id == player_id,
                    GoalscorerOddsSnapshot.provider == quote.provider,
                    GoalscorerOddsSnapshot.bookmaker == quote.bookmaker,
                    GoalscorerOddsSnapshot.observed_at == quote.observed_at,
                )
            )
            if existing is not None:
                continue
            self.session.add(
                GoalscorerOddsSnapshot(
                    fixture_id=fixture_id,
                    player_id=player_id,
                    provider=quote.provider,
                    bookmaker=quote.bookmaker,
                    decimal_odds=quote.decimal_odds,
                    observed_at=quote.observed_at,
                    imported_at=imported_at,
                    snapshot_kind=quote.snapshot_kind.value,
                    source_ref=quote.source_ref,
                )
            )
            inserted += 1
        return inserted

    def goalscorer_probabilities(
        self,
    ) -> dict[tuple[int, int], tuple[float, datetime, int]]:
        """Return median latest implied scorer probabilities by fixture and player."""

        grouped: dict[tuple[int, int], dict[str, GoalscorerOddsSnapshot]] = {}
        for row in self.session.scalars(select(GoalscorerOddsSnapshot)):
            books = grouped.setdefault((row.fixture_id, row.player_id), {})
            current = books.get(row.bookmaker)
            if current is None or row.observed_at > current.observed_at:
                books[row.bookmaker] = row
        return {
            key: (
                statistics.median(1.0 / row.decimal_odds for row in books.values()),
                _utc(max(row.observed_at for row in books.values())),
                len(books),
            )
            for key, books in grouped.items()
        }

    def save_market_forecasts(self, outputs: list[MarketFixtureOutput]) -> None:
        """Persist market fixture forecasts as an immutable run."""

        for output in outputs:
            self.session.add(
                MarketForecast(
                    fixture_id=output.fixture_id,
                    prediction_at=output.prediction_at,
                    input_cutoff_at=output.input_cutoff_at,
                    devig_method=output.devig_method,
                    home_win=output.home_win,
                    draw=output.draw,
                    away_win=output.away_win,
                    over_2_5=output.over_2_5,
                    btts_yes=output.btts_yes,
                    home_over_1_5=output.home_over_1_5,
                    away_over_1_5=output.away_over_1_5,
                    home_xg=output.home_xg,
                    away_xg=output.away_xg,
                    home_clean_sheet=output.home_clean_sheet,
                    away_clean_sheet=output.away_clean_sheet,
                    dispersion=output.dispersion,
                    bookmaker_count=output.bookmaker_count,
                    fit_residual=output.fit_residual,
                    fit_success=output.fit_success,
                    advanced_market_count=output.advanced_market_count,
                )
            )

    def save_player_market_forecasts(self, outputs: list[PlayerMarketOutput]) -> None:
        """Persist player market xPts independently from statistical forecasts."""

        for output in outputs:
            components = output.components
            self.session.add(
                PlayerMarketForecast(
                    player_id=output.player_id,
                    gameweek_id=output.gameweek_id,
                    prediction_at=output.prediction_at,
                    input_cutoff_at=output.input_cutoff_at,
                    appearance_xpts=components.appearance,
                    goal_xpts=components.goals,
                    assist_xpts=components.assists,
                    clean_sheet_xpts=components.clean_sheet,
                    save_xpts=components.saves,
                    bonus_xpts=components.bonus,
                    deduction_xpts=components.deductions,
                    market_xpts=components.total,
                    fixture_count=output.fixture_count,
                    confidence=output.confidence,
                    component_json=json.dumps(output.explanation, sort_keys=True),
                    goalscorer_probability=output.goalscorer_probability,
                )
            )

    def latest_market_forecasts(self) -> list[MarketForecast]:
        """Return fixture market forecasts from the latest complete run."""

        latest = self.session.scalar(select(func.max(MarketForecast.prediction_at)))
        if latest is None:
            return []
        return list(
            self.session.scalars(
                select(MarketForecast).where(MarketForecast.prediction_at == latest)
            )
        )

    def market_dashboard(self) -> list[dict[str, object]]:
        """Return the current market forecast dashboard read model."""

        latest = self.session.scalar(select(func.max(MarketForecast.prediction_at)))
        if latest is None:
            return []
        home = aliased(Team)
        away = aliased(Team)
        statement = (
            select(MarketForecast, Fixture, Gameweek, home, away)
            .join(Fixture, MarketForecast.fixture_id == Fixture.id)
            .outerjoin(Gameweek, Fixture.gameweek_id == Gameweek.id)
            .join(home, Fixture.home_team_id == home.id)
            .join(away, Fixture.away_team_id == away.id)
            .where(MarketForecast.prediction_at == latest)
            .order_by(Fixture.kickoff_at)
        )
        return [
            {
                "Gameweek": gameweek.name if gameweek else "Unscheduled",
                "Fixture ID": fixture.fpl_id,
                "Home": home_team.short_name,
                "Away": away_team.short_name,
                "Home win %": forecast.home_win * 100,
                "Draw %": forecast.draw * 100,
                "Away win %": forecast.away_win * 100,
                "Over 2.5 %": forecast.over_2_5 * 100,
                "BTTS %": forecast.btts_yes * 100 if forecast.btts_yes is not None else None,
                "Home over 1.5 %": (
                    forecast.home_over_1_5 * 100
                    if forecast.home_over_1_5 is not None
                    else None
                ),
                "Away over 1.5 %": (
                    forecast.away_over_1_5 * 100
                    if forecast.away_over_1_5 is not None
                    else None
                ),
                "Home xG": forecast.home_xg,
                "Away xG": forecast.away_xg,
                "Home CS %": forecast.home_clean_sheet * 100,
                "Away CS %": forecast.away_clean_sheet * 100,
                "Books": forecast.bookmaker_count,
                "Dispersion": forecast.dispersion,
                "Fit residual": forecast.fit_residual,
                "Advanced markets": forecast.advanced_market_count,
                "Fit": "Good"
                if forecast.fit_success and forecast.fit_residual < 0.05
                else "Review",
                "Updated": forecast.prediction_at,
            }
            for forecast, fixture, gameweek, home_team, away_team in self.session.execute(statement)
        ]

    def fixture_choices(self) -> list[tuple[int, str]]:
        """Return future FPL fixture IDs and human-readable labels."""

        home = aliased(Team)
        away = aliased(Team)
        statement = (
            select(Fixture.fpl_id, Gameweek.name, home.short_name, away.short_name)
            .join(home, Fixture.home_team_id == home.id)
            .join(away, Fixture.away_team_id == away.id)
            .outerjoin(Gameweek, Fixture.gameweek_id == Gameweek.id)
            .where(Fixture.status == "scheduled")
            .order_by(Fixture.kickoff_at)
        )
        return [
            (fixture_id, f"{gameweek or 'TBD'} · {home_name} vs {away_name} · #{fixture_id}")
            for fixture_id, gameweek, home_name, away_name in self.session.execute(statement)
        ]

    def quote_count(self) -> int:
        """Return the number of stored odds observations."""

        fixture_count = self.session.scalar(select(func.count(OddsSnapshot.id))) or 0
        scorer_count = self.session.scalar(select(func.count(GoalscorerOddsSnapshot.id))) or 0
        return fixture_count + scorer_count


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
