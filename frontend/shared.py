"""Shared Streamlit composition and data controls."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast

import streamlit as st

from fpl_optimizer.analytics.player_dataset import PlayerAnalyticsRecord
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.repositories import FplRepository
from fpl_optimizer.domain.strategy import StrategyMode, StrategyProfile
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

    st.set_page_config(
        page_title=f"{title} · FPL Optimizer",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        :root {
            --fpl-ink: #14241c;
            --fpl-muted: #66736c;
            --fpl-surface: #ffffff;
            --fpl-canvas: #f5f7f4;
            --fpl-border: #dfe6e1;
            --fpl-green: #087f5b;
            --fpl-green-soft: #e8f5ef;
        }
        .stApp {background: var(--fpl-canvas); color: var(--fpl-ink);}
        .block-container {
            max-width: 1180px;
            padding-top: 3.5rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3 {color: var(--fpl-ink); letter-spacing: -0.025em;}
        h1 {font-size: clamp(2rem, 3vw, 2.75rem) !important; margin-bottom: 0.15rem !important;}
        [data-testid="stCaptionContainer"] {color: var(--fpl-muted);}
        [data-testid="stMetric"] {
            background: var(--fpl-surface);
            border: 1px solid var(--fpl-border);
            border-radius: 0.9rem;
            padding: 1rem 1.1rem;
            box-shadow: 0 1px 2px rgba(20, 36, 28, 0.03);
        }
        [data-testid="stMetricLabel"] {color: var(--fpl-muted);}
        [data-testid="stMetricValue"] {color: var(--fpl-ink);}
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--fpl-surface);
            border-color: var(--fpl-border) !important;
            border-radius: 1rem;
        }
        [data-testid="stSidebar"] {
            background: #fbfcfa;
            border-right: 1px solid var(--fpl-border);
        }
        [data-testid="stSidebarNav"] {display: none;}
        [data-testid="stSidebar"] .block-container {padding-top: 1.25rem;}
        [data-testid="stSidebar"] hr {margin: 0.85rem 0;}
        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            border-radius: 0.6rem;
            padding: 0.42rem 0.55rem;
            text-decoration: none;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
            background: var(--fpl-green-soft);
            color: var(--fpl-green);
        }
        .fpl-brand {font-size: 1.12rem; font-weight: 750; color: var(--fpl-ink);}
        .fpl-kicker {
            color: var(--fpl-green);
            font-size: 0.75rem;
            font-weight: 750;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }
        .fpl-nav-label {
            color: var(--fpl-muted);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 0.8rem 0 0.25rem;
        }
        .freshness {color: var(--fpl-muted); font-size: 0.82rem;}
        div.stButton > button[kind="primary"] {font-weight: 700;}
        div[data-baseweb="tab-list"] {gap: 0.25rem;}
        div[data-baseweb="tab"] {border-radius: 0.55rem 0.55rem 0 0;}
        @media (max-width: 700px) {
            .block-container {padding-top: 3.25rem;}
            [data-testid="stMetric"] {padding: 0.8rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    container = get_container()
    data_sidebar(container)
    return container


def data_sidebar(container: AppContainer) -> None:
    """Render focused navigation with secondary data and model controls."""

    with container.database.session() as session:
        repository = FplRepository(session)
        freshness = repository.freshness()
        counts = repository.counts()
        forecast_freshness = ForecastRepository(session).latest_prediction_at()

    st.sidebar.markdown('<div class="fpl-brand">⚽ FPL Optimizer</div>', unsafe_allow_html=True)
    st.sidebar.caption("One clear decision for every Gameweek")

    st.sidebar.markdown('<div class="fpl-nav-label">Weekly workflow</div>', unsafe_allow_html=True)
    st.sidebar.page_link("streamlit_app.py", label="Overview", icon="🏠")
    st.sidebar.page_link("pages/14_Weekly_Dashboard.py", label="This Week", icon="📋")
    st.sidebar.page_link("pages/0_My_Team.py", label="My Team", icon="⚽")
    st.sidebar.page_link("pages/7_Transfers.py", label="Transfers", icon="🔁")
    st.sidebar.page_link("pages/8_Planner.py", label="Future Plan", icon="🗓️")

    with st.sidebar.expander("Explore players & fixtures"):
        st.page_link("pages/1_Players.py", label="Players", icon="👤")
        st.page_link("pages/2_Fixtures.py", label="Fixtures", icon="📅")
        st.page_link("pages/3_Forecasts.py", label="Forecasts", icon="📈")
        st.page_link("pages/13_Player_Analytics.py", label="Player Analytics", icon="🔎")

    with st.sidebar.expander("Advanced tools"):
        st.page_link("pages/5_Strategy.py", label="Strategy", icon="🎛️")
        st.page_link("pages/6_Optimizer.py", label="Build a Squad", icon="🧮")
        st.page_link("pages/9_Simulation.py", label="Simulation", icon="🎲")
        st.page_link("pages/10_Chips.py", label="Chips", icon="🃏")
        st.page_link("pages/16_What_If.py", label="What If", icon="🧭")
        st.page_link("pages/4_Markets.py", label="Markets", icon="📊")
        st.page_link("pages/11_Backtesting.py", label="Backtesting", icon="🧪")
        st.page_link("pages/15_Model_Lab.py", label="Model Lab", icon="🔬")
        st.page_link("pages/12_Data_Sources.py", label="Data Sources", icon="🔌")

    st.sidebar.divider()
    active_strategy = active_strategy_profile()
    st.sidebar.caption(
        f"**{active_strategy.preset}** strategy · {active_strategy.horizon}GW horizon"
    )

    with st.sidebar.expander("Data & model settings"):
        if freshness:
            st.caption(f"FPL data · {format_timestamp(freshness)}")
        else:
            st.warning("No FPL data loaded yet")
        if counts["players"]:
            st.caption(
                f"{counts['players']} players · {counts['teams']} teams · "
                f"{counts['fixtures']} fixtures"
            )
            if forecast_freshness:
                st.caption(f"Forecasts · {format_timestamp(forecast_freshness)}")

        if st.button("Refresh FPL data", width="stretch", key="sidebar_refresh_data"):
            try:
                with st.spinner("Refreshing official FPL data…"):
                    report = container.refresh.refresh(force=True)
                if report.stale:
                    st.warning("Live refresh failed; cached data is still available.")
                else:
                    st.success(f"Loaded {report.players} players and {report.fixtures} fixtures.")
                for warning in report.warnings:
                    st.warning(warning)
                st.rerun()
            except Exception as error:
                st.error(f"Refresh could not be completed: {error}")

        if counts["players"] and st.button(
            "Regenerate forecasts", width="stretch", key="sidebar_generate_forecasts"
        ):
            try:
                with st.spinner("Projecting the next six Gameweeks…"):
                    report = container.forecast.run(horizon=6)
                st.success(f"Generated {report.forecasts:,} projections.")
                st.rerun()
            except Exception as error:
                st.error(f"Forecasting could not be completed: {error}")

        if counts["players"]:
            st.slider(
                "Market influence",
                min_value=0,
                max_value=100,
                value=30,
                step=5,
                key="market_influence",
                help="Blends statistical and market xPts.",
            )


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


def load_player_analytics(container: AppContainer) -> tuple[PlayerAnalyticsRecord, ...]:
    """Load a freshness-keyed analytics dataset without recalculating forecasts."""

    with container.database.session() as session:
        players_updated = FplRepository(session).freshness()
        forecasts = ForecastRepository(session)
        forecast_updated = forecasts.latest_prediction_at()
        market_updated = forecasts.latest_market_prediction_at()
    profile = active_strategy_profile()
    return _cached_player_analytics(
        players_updated.isoformat() if players_updated else "",
        forecast_updated.isoformat() if forecast_updated else "",
        market_updated.isoformat() if market_updated else "",
        market_weight(),
        json.dumps(asdict(profile), sort_keys=True),
    )


def load_player_forecast_details(
    container: AppContainer, player_ids: set[int]
) -> dict[int, list[dict[str, object]]]:
    """Load selected-player Gameweek forecasts through a freshness-keyed cache."""

    with container.database.session() as session:
        forecasts = ForecastRepository(session)
        forecast_updated = forecasts.latest_prediction_at()
        market_updated = forecasts.latest_market_prediction_at()
    return _cached_player_forecast_details(
        tuple(sorted(player_ids)),
        forecast_updated.isoformat() if forecast_updated else "",
        market_updated.isoformat() if market_updated else "",
        market_weight(),
    )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_player_analytics(
    players_updated: str,
    forecast_updated: str,
    market_updated: str,
    selected_market_weight: float,
    profile_json: str,
) -> tuple[PlayerAnalyticsRecord, ...]:
    """Cache the joined read model; timestamp arguments form the invalidation key."""

    del players_updated, forecast_updated, market_updated
    value = json.loads(profile_json)
    profile = StrategyProfile(
        name=str(value["name"]),
        mode=cast(StrategyMode, value["mode"]),
        preset=str(value["preset"]),
        horizon=int(value["horizon"]),
        risk_appetite=int(value["risk_appetite"]),
        transfer_reluctance=int(value["transfer_reluctance"]),
        ownership_preference=int(value["ownership_preference"]),
        weights={str(key): int(weight) for key, weight in value["weights"].items()},
    )
    return get_container().analytics.dataset(profile, selected_market_weight)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_player_forecast_details(
    player_ids: tuple[int, ...],
    forecast_updated: str,
    market_updated: str,
    selected_market_weight: float,
) -> dict[int, list[dict[str, object]]]:
    """Cache one batch read of persisted per-Gameweek forecast details."""

    del forecast_updated, market_updated
    with get_container().database.session() as session:
        return ForecastRepository(session).player_comparison_details(
            set(player_ids), selected_market_weight
        )


def require_data(rows: list[Any], noun: str) -> bool:
    """Render a useful empty state and return whether data exists."""

    if rows:
        return True
    st.info(f"No {noun} are loaded. Use **Refresh FPL data** in the sidebar to begin.")
    return False
