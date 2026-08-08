"""Player explorer, raw comparison table, and normalized radar analytics."""

from __future__ import annotations

from typing import cast

import pandas as pd
import streamlit as st
from components.player_filters import render_player_filters
from components.radar_chart import player_radar_figure
from shared import format_timestamp, load_player_analytics, page_setup, require_data

from fpl_optimizer.analytics.comparison import (
    UNIVERSE_OPTIONS,
    ComparisonUniverse,
    available_radar_metrics,
    comparison_rows,
    default_radar_metrics,
    radar_profiles,
)
from fpl_optimizer.analytics.filters import filter_players
from fpl_optimizer.analytics.metrics import metric_definition
from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.repositories import FplRepository


def _column_config() -> dict[str, object]:
    return {
        "Price": st.column_config.NumberColumn(format="£%.1fm"),
        "Ownership %": st.column_config.NumberColumn(format="%.1f%%"),
        "Expected minutes": st.column_config.NumberColumn(format="%.0f"),
        "Start probability %": st.column_config.NumberColumn(format="%.0f%%"),
        "Goal probability %": st.column_config.NumberColumn(format="%.1f%%"),
        "Goal xPts": st.column_config.NumberColumn(format="%.2f"),
        "Assist xPts": st.column_config.NumberColumn(format="%.2f"),
        "Clean sheet xPts": st.column_config.NumberColumn(format="%.2f"),
        "Save xPts": st.column_config.NumberColumn(format="%.2f"),
        "Bonus xPts": st.column_config.NumberColumn(format="%.2f"),
        "Attacking xPts": st.column_config.NumberColumn(format="%.2f"),
        "Stat xPts": st.column_config.NumberColumn(format="%.1f"),
        "Market xPts": st.column_config.NumberColumn(format="%.1f"),
        "Blended xPts": st.column_config.NumberColumn(format="%.1f"),
        "3GW xPts": st.column_config.NumberColumn(format="%.1f"),
        "5GW xPts": st.column_config.NumberColumn(format="%.1f"),
        "6GW xPts": st.column_config.NumberColumn(format="%.1f"),
        "Value": st.column_config.NumberColumn(format="%.1f"),
        "Risk": st.column_config.NumberColumn(format="%.0f/100"),
        "Optimization Score": st.column_config.ProgressColumn(
            min_value=0,
            max_value=100,
            format="%.1f",
        ),
        "Points": st.column_config.NumberColumn(format="%.0f"),
        "Form": st.column_config.NumberColumn(format="%.1f"),
        "Points/game": st.column_config.NumberColumn(format="%.1f"),
    }


DEFAULT_EXPLORER_COLUMNS = (
    "Full Name",
    "Team",
    "Position",
    "Price",
    "Ownership %",
    "Expected minutes",
    "Start probability %",
    "Blended xPts",
    "3GW xPts",
    "5GW xPts",
    "Value",
    "Risk",
    "Optimization Score",
)

EXPLORER_COLUMNS = (
    *DEFAULT_EXPLORER_COLUMNS,
    "Opponent",
    "Goal probability %",
    "Goal xPts",
    "Assist xPts",
    "Clean sheet xPts",
    "Save xPts",
    "Bonus xPts",
    "Attacking xPts",
    "Stat xPts",
    "Market xPts",
    "6GW xPts",
    "Points",
    "Form",
    "Points/game",
    "Forecast confidence",
    "Status",
)

container = page_setup("Player Analytics", "🔎")
st.title("Player Analytics")
st.caption("Explore players, compare raw forecasts, and inspect favorable 0–100 percentiles")

with container.database.session() as session:
    player_updated = FplRepository(session).freshness()
    forecast_repository = ForecastRepository(session)
    forecast_updated = forecast_repository.latest_prediction_at()
    market_updated = forecast_repository.latest_market_prediction_at()

freshness_parts = []
if player_updated:
    freshness_parts.append(f"FPL data {format_timestamp(player_updated)}")
if forecast_updated:
    freshness_parts.append(f"forecast {format_timestamp(forecast_updated)}")
if market_updated:
    freshness_parts.append(f"market {format_timestamp(market_updated)}")
if freshness_parts:
    st.caption(" · ".join(freshness_parts))

records = load_player_analytics(container)
if not require_data(list(records), "players"):
    st.stop()

if not any(record.blended_xpts is not None for record in records):
    st.info(
        "Generate advanced forecasts from the sidebar to unlock forecast-specific comparison "
        "dimensions. Season form, price, ownership, and points remain available."
    )

filters = render_player_filters(records, key_prefix="analytics")
filtered_records = filter_players(records, filters)
st.write(f"{len(filtered_records)} of {len(records)} players match the current filters")

valid_compare_ids = {record.player_id for record in filtered_records}
saved_compare_ids = st.session_state.get("analytics_compare_ids", [])
if isinstance(saved_compare_ids, list):
    st.session_state["analytics_compare_ids"] = [
        player_id for player_id in saved_compare_ids if player_id in valid_compare_ids
    ]

labels = {
    record.player_id: f"{record.full_name} · {record.team} · {record.position}"
    for record in filtered_records
}
selected_ids = st.multiselect(
    "Compare players",
    options=list(labels),
    format_func=lambda player_id: labels[player_id],
    max_selections=5,
    placeholder="Choose 2–5 players from the filtered results",
    key="analytics_compare_ids",
)
selected = tuple(record for record in records if record.player_id in selected_ids)

explorer_tab, compare_tab = st.tabs(["Explorer", "Compare"])

with explorer_tab:
    with st.expander("Choose table columns"):
        displayed_columns = st.multiselect(
            "Columns",
            options=list(EXPLORER_COLUMNS),
            default=list(DEFAULT_EXPLORER_COLUMNS),
            key="analytics_explorer_columns",
            label_visibility="collapsed",
        )
    if not displayed_columns:
        st.info("Choose at least one column to display the player explorer.")
    else:
        frame = pd.DataFrame(record.as_row() for record in filtered_records)
        st.dataframe(
            frame[list(displayed_columns)],
            hide_index=True,
            width="stretch",
            column_config=_column_config(),
        )
        st.caption("Select column headers to sort the current filtered results.")

with compare_tab:
    if len(selected) < 2:
        st.info("Choose at least two players above to open the comparison table and radar chart.")
    else:
        st.subheader("Raw metric comparison")
        comparison_frame = pd.DataFrame(comparison_rows(selected)).dropna(axis=1, how="all")
        st.dataframe(
            comparison_frame,
            hide_index=True,
            width="stretch",
            column_config=_column_config(),
        )
        st.caption(
            "Table values use their original units. Missing market-only values are omitted rather "
            "than estimated."
        )

        st.subheader("Radar comparison")
        available_metrics = available_radar_metrics(selected)
        if len(available_metrics) < 3:
            st.warning("At least three shared numeric metrics are required for a radar chart.")
        else:
            metric_state = st.session_state.get("analytics_radar_metrics")
            valid_metric_state = (
                [key for key in metric_state if key in available_metrics]
                if isinstance(metric_state, list)
                else []
            )
            if not 3 <= len(valid_metric_state) <= 10:
                valid_metric_state = list(default_radar_metrics(selected))
            st.session_state["analytics_radar_metrics"] = valid_metric_state

            same_position = len({record.position for record in selected}) == 1
            universe_options = list(UNIVERSE_OPTIONS)
            if not same_position:
                universe_options.remove("Same Position")
            current_universe = st.session_state.get("analytics_radar_universe")
            if current_universe not in universe_options:
                st.session_state["analytics_radar_universe"] = (
                    "Same Position" if same_position else "All Players"
                )

            controls = st.columns([1, 2])
            universe = controls[0].selectbox(
                "Compare against",
                options=universe_options,
                key="analytics_radar_universe",
                help="The player group used to calculate each percentile.",
            )
            metric_keys = controls[1].multiselect(
                "Choose metrics",
                options=list(available_metrics),
                format_func=lambda key: metric_definition(key).comparison_label,
                max_selections=10,
                key="analytics_radar_metrics",
                help="Choose between three and ten dimensions.",
            )
            if len(metric_keys) < 3:
                st.warning("Choose at least three radar dimensions.")
            else:
                profiles = radar_profiles(
                    selected,
                    records,
                    tuple(metric_keys),
                    cast(ComparisonUniverse, universe),
                )
                st.plotly_chart(
                    player_radar_figure(profiles),
                    width="stretch",
                    config={
                        "displaylogo": False,
                        "responsive": True,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                    },
                )
                st.caption(
                    f"Normalized as tie-aware percentiles against **{universe}**. Higher is always "
                    "more favorable: Risk becomes Reliability, Price becomes Affordability, and "
                    "Ownership becomes Differential Appeal. Hover for raw values and units."
                )
                with st.expander("How these dimensions are calculated"):
                    for key in metric_keys:
                        definition = metric_definition(key)
                        st.markdown(
                            f"**{definition.comparison_label}** — {definition.description} "
                            f"Raw unit: `{definition.unit}`."
                        )
