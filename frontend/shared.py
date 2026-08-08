"""Shared Streamlit composition and data controls."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import streamlit as st

from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.logging import configure_logging
from fpl_optimizer.scoring.presets import preset_profile
from fpl_optimizer.services.container import AppContainer


@st.cache_resource
def get_container() -> AppContainer:
    """Create one dependency container per Streamlit process."""

    container = AppContainer.create()
    configure_logging(container.settings.log_level)
    return container


def page_setup(title: str, icon: str) -> AppContainer:
    """Set consistent page chrome and return the application container."""

    st.set_page_config(page_title=f"{title} · FPL Optimizer", page_icon=icon, layout="wide")
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem; padding-bottom: 3rem;}
        [data-testid="stMetric"] {background: #f5f7f9; border-radius: 0.75rem; padding: 1rem;}
        .freshness {color: #5f6b76; font-size: 0.88rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    container = get_container()
    data_sidebar(container)
    return container


def data_sidebar(container: AppContainer) -> None:
    """Render refresh, freshness, and navigation guidance."""

    with container.database.session() as session:
        repository = FplRepository(session)
        freshness = repository.freshness()
        counts = repository.counts()
        forecast_freshness = ForecastRepository(session).latest_prediction_at()

    st.sidebar.title("FPL Optimizer")
    if freshness:
        st.sidebar.caption(f"Data updated {format_timestamp(freshness)}")
    else:
        st.sidebar.warning("No FPL data loaded yet")

    if st.sidebar.button("Refresh FPL data", type="primary", width="stretch"):
        try:
            with st.spinner("Refreshing official FPL data…"):
                report = container.refresh.refresh(force=True)
            if report.stale:
                st.sidebar.warning("Live refresh failed; cached data is still available.")
            else:
                st.sidebar.success(
                    f"Loaded {report.players} players and {report.fixtures} fixtures."
                )
            for warning in report.warnings:
                st.sidebar.warning(warning)
            st.rerun()
        except Exception as error:
            st.sidebar.error(f"Refresh could not be completed: {error}")

    if counts["players"]:
        st.sidebar.caption(
            f"{counts['players']} players · {counts['teams']} teams · {counts['fixtures']} fixtures"
        )
        if forecast_freshness:
            st.sidebar.caption(f"Forecasted {format_timestamp(forecast_freshness)}")
        if st.sidebar.button("Generate advanced forecasts", width="stretch"):
            try:
                with st.spinner("Projecting advanced xPts for the next six Gameweeks…"):
                    report = container.forecast.run(horizon=6)
                st.sidebar.success(
                    f"Generated {report.forecasts:,} projections with model {report.model_version}."
                )
                st.rerun()
            except Exception as error:
                st.sidebar.error(f"Forecasting could not be completed: {error}")
        st.sidebar.subheader("Forecast model")
        st.sidebar.slider(
            "Market influence",
            min_value=0,
            max_value=100,
            value=30,
            step=5,
            key="market_influence",
            help=("Blends statistical and market xPts. It does not change strategy preferences."),
        )
    st.sidebar.divider()
    active_strategy = active_strategy_profile()
    st.sidebar.caption(
        f"Strategy: {active_strategy.preset} · {active_strategy.horizon}GW · "
        f"{active_strategy.mode.title()}"
    )
    st.sidebar.divider()
    st.sidebar.caption("Live team import · Live odds · Phase 12 calibration")


def format_timestamp(value: datetime) -> str:
    """Format a database timestamp consistently as UTC."""

    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%d %b %Y, %H:%M UTC")


def load_players(container: AppContainer) -> list[dict[str, object]]:
    """Load current players from the application repository."""

    with container.database.session() as session:
        return FplRepository(session).list_players()


def load_fixtures(container: AppContainer) -> list[dict[str, object]]:
    """Load fixtures from the application repository."""

    with container.database.session() as session:
        return FplRepository(session).list_fixtures()


def load_forecast_summaries(
    container: AppContainer, selected_market_weight: float | None = None
) -> list[dict[str, object]]:
    """Load current-run player forecast summaries."""

    weight = (
        selected_market_weight
        if selected_market_weight is not None
        else float(st.session_state.get("market_influence", 30)) / 100.0
    )
    with container.database.session() as session:
        return ForecastRepository(session).list_player_summaries(weight)


def market_weight() -> float:
    """Return the current forecast blend as a zero-to-one weight."""

    return float(st.session_state.get("market_influence", 30)) / 100.0


def active_strategy_profile() -> StrategyProfile:
    """Return the working strategy saved in this browser session."""

    value = st.session_state.get("active_strategy")
    if not isinstance(value, dict):
        return preset_profile("Balanced", "simple")
    return StrategyProfile(
        name=str(value["name"]),
        mode=value["mode"],
        preset=str(value["preset"]),
        horizon=int(value["horizon"]),
        risk_appetite=int(value["risk_appetite"]),
        transfer_reluctance=int(value["transfer_reluctance"]),
        ownership_preference=int(value["ownership_preference"]),
        weights={str(key): int(weight) for key, weight in value["weights"].items()},
    )


def load_strategy_scores(container: AppContainer) -> list[dict[str, object]]:
    """Calculate current-session strategy scores for presentation."""

    scores = container.strategy.score(active_strategy_profile(), market_weight())
    return [
        {
            "Player ID": score.player_id,
            "Optimization Score": score.score,
            "Value": score.value,
            "Risk": score.risk,
        }
        for score in scores
    ]


def require_data(rows: list[Any], noun: str) -> bool:
    """Render a useful empty state and return whether data exists."""

    if rows:
        return True
    st.info(f"No {noun} are loaded. Use **Refresh FPL data** in the sidebar to begin.")
    return False
