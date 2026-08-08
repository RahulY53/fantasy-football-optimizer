"""Live EPL event matching, odds parsing, persistence, and market refresh."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import aliased

from fpl_optimizer.database.base import Database
from fpl_optimizer.database.models import Fixture, Gameweek, OddsSnapshot, Team
from fpl_optimizer.domain.enums import OddsMarket, OddsSelection, OddsSnapshotKind
from fpl_optimizer.domain.markets import GoalscorerOddsQuote, OddsQuote
from fpl_optimizer.odds.aliases import TeamAliases
from fpl_optimizer.odds.fixture_matcher import (
    FplFixtureIdentity,
    VendorEvent,
    match_fixture,
)
from fpl_optimizer.odds.providers.base import LiveOddsProvider
from fpl_optimizer.services.markets import MarketRunReport, MarketService, OddsImportService


@dataclass(frozen=True, slots=True)
class LiveOddsRefreshReport:
    """Summary of one cached/live EPL odds synchronization."""

    events: int
    matched: int
    rejected: int
    quotes: int
    inserted: int
    from_cache: bool
    market_report: MarketRunReport | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiveOddsStatus:
    """Configuration and persisted freshness for the settings screen."""

    configured: bool
    provider: str
    last_sync: datetime | None
    stale: bool


class _QuoteProvider:
    name = "live"

    def __init__(self, quotes: list[OddsQuote]) -> None:
        self.quotes: list[OddsQuote | GoalscorerOddsQuote] = list(quotes)

    def get_quotes(self) -> list[OddsQuote | GoalscorerOddsQuote]:
        return self.quotes


class LiveOddsUpdateService:
    """Keep live odds modular while feeding the existing market forecast layer."""

    def __init__(
        self,
        database: Database,
        provider: LiveOddsProvider,
        aliases_path: Path,
        *,
        configured: bool,
        stale_after_seconds: int = 7200,
    ) -> None:
        self.database = database
        self.provider = provider
        self.aliases = TeamAliases(aliases_path)
        self.configured = configured
        self.stale_after_seconds = stale_after_seconds
        self.importer = OddsImportService(database)
        self.markets = MarketService(database)

    def test_connection(self) -> bool:
        """Test provider connectivity using its normal cache policy."""

        return self.provider.test_connection()

    def refresh(self, *, force: bool = False) -> LiveOddsRefreshReport:
        """Fetch EPL events, confidence-match fixtures, and rebuild market forecasts."""

        fixtures, deadlines = self._fixtures()
        raw_events = self.provider.get_events(force=force)
        matches: dict[int, int] = {}
        rejected = 0
        warnings: list[str] = []
        for raw in raw_events:
            try:
                event = parse_event(raw)
            except ValueError as error:
                warnings.append(str(error))
                rejected += 1
                continue
            match = match_fixture(event, fixtures, self.aliases)
            if match is None:
                warnings.append(f"Rejected unmatched event: {event.home} vs {event.away}")
                rejected += 1
                continue
            matches[event.event_id] = match.fixture_fpl_id
        raw_odds = self.provider.get_event_odds(list(matches), force=force) if matches else []
        quotes: list[OddsQuote] = []
        for payload in raw_odds:
            event_id = int(payload.get("id") or 0)
            fixture_id = matches.get(event_id)
            if fixture_id is None:
                continue
            parsed = parse_event_odds(payload, fixture_id)
            deadline = deadlines.get(fixture_id)
            quotes.extend(
                replace(
                    quote,
                    snapshot_kind=(
                        OddsSnapshotKind.PRE_DEADLINE
                        if deadline is not None and quote.observed_at <= deadline
                        else OddsSnapshotKind.CURRENT
                    ),
                )
                for quote in parsed
            )
        if not quotes:
            return LiveOddsRefreshReport(
                len(raw_events), len(matches), rejected, 0, 0, _from_cache(self.provider), None,
                tuple(warnings + ["No complete supported live markets were returned."]),
            )
        imported = self.importer.import_provider(_QuoteProvider(quotes))
        market_report: MarketRunReport | None = None
        try:
            market_report = self.markets.run()
        except RuntimeError as error:
            warnings.append(str(error))
        return LiveOddsRefreshReport(
            len(raw_events), len(matches), rejected, len(quotes), imported.inserted,
            _from_cache(self.provider), market_report, tuple(warnings)
        )

    def status(self) -> LiveOddsStatus:
        """Return configuration and latest persisted provider sync age."""

        with self.database.session() as session:
            latest = session.scalar(
                select(OddsSnapshot.imported_at)
                .where(OddsSnapshot.provider == self.provider.name)
                .order_by(OddsSnapshot.imported_at.desc())
                .limit(1)
            )
        aware = latest if latest is None or latest.tzinfo else latest.replace(tzinfo=UTC)
        stale = aware is None or datetime.now(UTC) - aware > timedelta(
            seconds=self.stale_after_seconds
        )
        return LiveOddsStatus(self.configured, self.provider.name, aware, stale)

    def _fixtures(self) -> tuple[list[FplFixtureIdentity], dict[int, datetime]]:
        home, away = aliased(Team), aliased(Team)
        with self.database.session() as session:
            rows = list(
                session.execute(
                    select(Fixture, home, away, Gameweek)
                    .join(home, Fixture.home_team_id == home.id)
                    .join(away, Fixture.away_team_id == away.id)
                    .outerjoin(Gameweek, Fixture.gameweek_id == Gameweek.id)
                    .where(Fixture.status == "scheduled", Fixture.kickoff_at.is_not(None))
                )
            )
        fixtures = [
            FplFixtureIdentity(
                fixture.fpl_id,
                home_team.name,
                away_team.name,
                _utc(fixture.kickoff_at),
            )
            for fixture, home_team, away_team, _ in rows
            if fixture.kickoff_at is not None
        ]
        deadlines = {
            fixture.fpl_id: _utc(gameweek.deadline_at)
            for fixture, _, _, gameweek in rows
            if gameweek is not None
        }
        return fixtures, deadlines


def parse_event(payload: dict[str, Any]) -> VendorEvent:
    """Parse one provider event with explicit league and timestamp validation."""

    try:
        league = payload["league"]
        return VendorEvent(
            event_id=int(payload["id"]),
            home=str(payload["home"]),
            away=str(payload["away"]),
            kickoff_at=_parse_time(str(payload["date"])),
            league=str(league.get("name") or league.get("slug")),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Odds provider returned a malformed EPL event") from error


def parse_event_odds(payload: dict[str, Any], fixture_fpl_id: int) -> list[OddsQuote]:
    """Parse independent bookmaker ML and 2.5-total snapshots."""

    bookmakers = payload.get("bookmakers")
    if not isinstance(bookmakers, dict):
        return []
    quotes: list[OddsQuote] = []
    for bookmaker, markets in bookmakers.items():
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict):
                continue
            name = str(market.get("name") or "").lower()
            odds_rows = market.get("odds")
            if not isinstance(odds_rows, list):
                continue
            observed = _parse_time(str(market.get("updatedAt") or payload.get("date")))
            for odds in odds_rows:
                if not isinstance(odds, dict):
                    continue
                if name in {"ml", "moneyline", "1x2"}:
                    quotes.extend(
                        _quotes(
                            fixture_fpl_id,
                            str(bookmaker),
                            OddsMarket.MATCH_RESULT,
                            odds,
                            (
                                ("home", OddsSelection.HOME),
                                ("draw", OddsSelection.DRAW),
                                ("away", OddsSelection.AWAY),
                            ),
                            observed,
                            int(payload.get("id") or 0),
                        )
                    )
                elif "total" in name or "over" in name:
                    line = odds.get("hdp", odds.get("line", odds.get("total", 2.5)))
                    if abs(float(str(line)) - 2.5) > 0.01:
                        continue
                    quotes.extend(
                        _quotes(
                            fixture_fpl_id,
                            str(bookmaker),
                            OddsMarket.TOTAL_GOALS_2_5,
                            odds,
                            (("over", OddsSelection.OVER), ("under", OddsSelection.UNDER)),
                            observed,
                            int(payload.get("id") or 0),
                        )
                    )
    return quotes


def _quotes(
    fixture_id: int,
    bookmaker: str,
    market: OddsMarket,
    values: dict[str, Any],
    selections: tuple[tuple[str, OddsSelection], ...],
    observed: datetime,
    event_id: int,
) -> list[OddsQuote]:
    results: list[OddsQuote] = []
    for key, selection in selections:
        try:
            price = float(values[key])
        except (KeyError, TypeError, ValueError):
            return []
        if price <= 1:
            return []
        results.append(
            OddsQuote(
                fixture_fpl_id=fixture_id,
                provider="odds_api_io",
                bookmaker=bookmaker,
                market=market,
                selection=selection,
                decimal_odds=price,
                observed_at=observed,
                source_ref=f"Odds-API.io event {event_id}",
            )
        )
    return results


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _utc(parsed)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _from_cache(provider: LiveOddsProvider) -> bool:
    return bool(getattr(provider, "last_from_cache", False))
