"""Read-only persistence adapter for the advanced Model Lab."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpl_optimizer.database.models import (
    BacktestRun,
    Gameweek,
    ModelVersion,
    Player,
    PlayerForecast,
    PlayerMarketForecast,
    Team,
)
from fpl_optimizer.domain.model_lab import ModelVersionSummary, PlayerModelDiagnostic
from fpl_optimizer.domain.names import resolved_player_name


class ModelLabRepository:
    """Inspect immutable model artifacts without updating application state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def versions(self) -> tuple[ModelVersionSummary, ...]:
        """Return model metadata with only persisted, non-secret parameters."""

        counts: dict[int, int] = {
            model_id: int(count)
            for model_id, count in self.session.execute(
                select(PlayerForecast.model_version_id, func.count(PlayerForecast.id)).group_by(
                    PlayerForecast.model_version_id
                )
            )
        }
        rows = self.session.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc()))
        return tuple(
            ModelVersionSummary(
                name=row.name,
                semantic_version=row.semantic_version,
                feature_schema=row.feature_schema,
                code_revision=row.code_revision,
                created_at=row.created_at,
                training_cutoff_at=row.training_cutoff_at,
                forecast_rows=int(counts.get(row.id, 0)),
                parameters=_safe_parameters(row.parameter_json),
            )
            for row in rows
        )

    def diagnostics(self, market_weight: float) -> tuple[PlayerModelDiagnostic, ...]:
        """Return first-horizon diagnostics from the latest cached forecast runs."""

        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("Market weight must be between 0 and 1")
        latest = self.latest_forecast_at()
        if latest is None:
            return ()
        statistical = list(
            self.session.execute(
                select(PlayerForecast, Player, Team, Gameweek, ModelVersion)
                .join(Player, PlayerForecast.player_id == Player.id)
                .join(Team, Player.team_id == Team.id)
                .join(Gameweek, PlayerForecast.gameweek_id == Gameweek.id)
                .join(ModelVersion, PlayerForecast.model_version_id == ModelVersion.id)
                .where(PlayerForecast.prediction_at == latest)
                .order_by(Player.id, Gameweek.fpl_id)
            )
        )
        market_latest = self.latest_market_forecast_at()
        market_by_key: dict[tuple[int, int], PlayerMarketForecast] = {}
        if market_latest is not None:
            market_by_key = {
                (row.player_id, row.gameweek_id): row
                for row in self.session.scalars(
                    select(PlayerMarketForecast).where(
                        PlayerMarketForecast.prediction_at == market_latest
                    )
                )
            }
        output: list[PlayerModelDiagnostic] = []
        seen: set[int] = set()
        for forecast, player, team, gameweek, version in statistical:
            if player.id in seen:
                continue
            seen.add(player.id)
            explanation = _json_object(forecast.component_json)
            market = market_by_key.get((player.id, gameweek.id))
            market_xpts = market.market_xpts if market else None
            blended = (
                forecast.stat_xpts
                if market_xpts is None
                else forecast.stat_xpts * (1.0 - market_weight) + market_xpts * market_weight
            )
            output.append(
                PlayerModelDiagnostic(
                    player_id=player.id,
                    player=resolved_player_name(
                        player.display_name,
                        player.first_name,
                        player.second_name,
                        player.web_name,
                    ),
                    team=team.short_name,
                    position=player.position,
                    gameweek=gameweek.name,
                    opponent=forecast.opponent_summary,
                    status=player.status,
                    expected_minutes=forecast.expected_minutes,
                    start_probability=_as_float(explanation.get("p_start")),
                    confidence=forecast.confidence,
                    stat_xpts=forecast.stat_xpts,
                    market_xpts=market_xpts,
                    blended_xpts=blended,
                    market_edge=(
                        market_xpts - forecast.stat_xpts
                        if market_xpts is not None
                        else None
                    ),
                    model_version=f"{version.name} {version.semantic_version}",
                )
            )
        return tuple(output)

    def latest_forecast_at(self) -> datetime | None:
        """Return latest statistical forecast timestamp."""

        return self.session.scalar(select(func.max(PlayerForecast.prediction_at)))

    def latest_market_forecast_at(self) -> datetime | None:
        """Return latest market forecast timestamp."""

        return self.session.scalar(select(func.max(PlayerMarketForecast.prediction_at)))

    def latest_backtest(self) -> dict[str, object] | None:
        """Return the latest persisted detailed backtest payload."""

        row = self.session.scalar(
            select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(1)
        )
        if row is None:
            return None
        payload = _json_object(row.result_json)
        payload["run_id"] = row.id
        payload["created_at"] = row.created_at
        return payload


def _json_object(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _safe_parameters(value: str) -> tuple[tuple[str, str], ...]:
    """Render scalar model parameters while rejecting credential-like keys."""

    blocked_fragments = ("key", "secret", "token", "password", "url", "path")
    parsed = _json_object(value)
    return tuple(
        (str(key), str(item))
        for key, item in sorted(parsed.items())
        if not any(fragment in str(key).lower() for fragment in blocked_fragments)
        and isinstance(item, (str, int, float, bool))
    )


def _as_float(value: object) -> float:
    return float(value) if isinstance(value, (int, float, str)) else 0.0
