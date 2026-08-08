"""Player explorer, raw comparison table, and normalized radar analytics."""

from __future__ import annotations

from typing import cast

import pandas as pd
import streamlit as st
from components.forecast_chart import ForecastChartMode, player_forecast_figure
from components.matrix_chart import (
    ColorMode,
    LabelMode,
    SizeMode,
    player_matrix_figure,
)
from components.player_filters import render_player_filters
from components.radar_chart import player_radar_figure
from shared import (
    format_timestamp,
    load_player_analytics,
    load_player_forecast_details,
    page_setup,
    require_data,
)

from fpl_optimizer.analytics.comparison import (
    UNIVERSE_OPTIONS,
    ComparisonUniverse,
    available_radar_metrics,
    comparison_rows,
    default_radar_metrics,
    radar_profiles,
)
from fpl_optimizer.analytics.filters import filter_players
from fpl_optimizer.analytics.forecast_comparison import (
    FORECAST_HORIZONS,
    build_forecast_comparison,
    fixture_comparison_rows,
    forecast_export_rows,
)
from fpl_optimizer.analytics.matrix import (
    MATRIX_PRESETS,
    REFERENCE_METHODS,
    ReferenceMethod,
    available_matrix_metrics,
    available_matrix_presets,
    build_matrix,
)
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
        "Market edge": st.column_config.NumberColumn(format="%+.1f"),
        "Stat xPts": st.column_config.NumberColumn(format="%.1f"),
        "Market xPts": st.column_config.NumberColumn(format="%.1f"),
        "Blended xPts": st.column_config.NumberColumn(format="%.1f"),
        "3GW xPts": st.column_config.NumberColumn(format="%.1f"),
        "5GW xPts": st.column_config.NumberColumn(format="%.1f"),
        "6GW xPts": st.column_config.NumberColumn(format="%.1f"),
        "5GW xPts / £m": st.column_config.NumberColumn(format="%.2f"),
        "Next-GW xPts / 90": st.column_config.NumberColumn(format="%.2f"),
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
    "Market edge",
    "6GW xPts",
    "5GW xPts / £m",
    "Next-GW xPts / 90",
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

explorer_tab, compare_tab, matrix_tab, forecast_tab = st.tabs(
    ["Explorer", "Compare", "2×2 Matrix", "Forecast"]
)

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
        export_columns = list(
            dict.fromkeys(
                ("Player ID", *EXPLORER_COLUMNS, "Web Name", "News", "Updated")
            )
        )
        st.download_button(
            "Download filtered players (CSV)",
            frame[[column for column in export_columns if column in frame]].to_csv(
                index=False
            ),
            file_name="fpl-player-analytics.csv",
            mime="text/csv",
            key="analytics_filtered_csv",
        )

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
        st.download_button(
            "Download comparison (CSV)",
            comparison_frame.to_csv(index=False),
            file_name="fpl-player-comparison.csv",
            mime="text/csv",
            key="analytics_comparison_csv",
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

with matrix_tab:
    st.subheader("Interactive 2×2 player matrix")
    st.caption(
        "Choose a population and plot any two available metrics. All normal player filters "
        "continue to apply."
    )
    selection_mode = st.radio(
        "Players to plot",
        (
            "Filtered players",
            "Selected players",
            "Position",
            "Team",
            "Current squad",
            "Optimizer candidates",
        ),
        horizontal=True,
        key="matrix_selection_mode",
    )

    matrix_records = filtered_records
    if selection_mode == "Selected players":
        matrix_records = tuple(
            record for record in filtered_records if record.player_id in selected_ids
        )
    elif selection_mode == "Position":
        position_options = sorted({record.position for record in filtered_records})
        if position_options:
            selected_position = st.selectbox(
                "Matrix position",
                position_options,
                key="matrix_population_position",
            )
            matrix_records = tuple(
                record for record in filtered_records if record.position == selected_position
            )
        else:
            matrix_records = ()
    elif selection_mode == "Team":
        team_options = sorted({record.team for record in filtered_records})
        selected_matrix_teams = st.multiselect(
            "Matrix teams",
            team_options,
            key="matrix_population_teams",
        )
        matrix_records = tuple(
            record for record in filtered_records if record.team in selected_matrix_teams
        )
    elif selection_mode == "Current squad":
        current_team = container.team.get()
        current_ids = (
            {player.player_id for player in current_team.players} if current_team else set()
        )
        matrix_records = tuple(
            record for record in filtered_records if record.player_id in current_ids
        )
        if current_team is None:
            st.info("Save or import My Team before using the Current squad matrix mode.")
    elif selection_mode == "Optimizer candidates":
        candidate_count = st.slider(
            "Top optimization candidates",
            min_value=5,
            max_value=min(100, max(5, len(filtered_records))),
            value=min(30, max(5, len(filtered_records))),
            step=5,
            key="matrix_candidate_count",
        )
        ranked_candidates = sorted(
            (record for record in filtered_records if record.optimization_score is not None),
            key=lambda record: record.optimization_score or 0.0,
            reverse=True,
        )
        matrix_records = tuple(ranked_candidates[:candidate_count])
        if not ranked_candidates:
            st.info("Generate forecasts to calculate optimization candidates.")

    if len(matrix_records) < 2:
        st.info("Choose a matrix population containing at least two players.")
    else:
        st.write(f"Plot population: **{len(matrix_records)} players**")
        available_metrics = available_matrix_metrics(matrix_records)
        available_presets = available_matrix_presets(matrix_records)
        preset_keys = ["custom", *(preset.key for preset in available_presets)]
        current_preset = st.session_state.get("matrix_preset")
        if current_preset not in preset_keys:
            st.session_state["matrix_preset"] = (
                "value_map" if "value_map" in preset_keys else "custom"
            )
        preset_key = st.selectbox(
            "Analysis view",
            preset_keys,
            format_func=lambda key: "Custom axes" if key == "custom" else MATRIX_PRESETS[key].label,
            key="matrix_preset",
        )

        previous_preset = st.session_state.get("matrix_applied_preset")
        if preset_key != "custom" and preset_key != previous_preset:
            selected_preset = MATRIX_PRESETS[preset_key]
            st.session_state["matrix_x_axis"] = selected_preset.x_metric
            st.session_state["matrix_y_axis"] = selected_preset.y_metric
        st.session_state["matrix_applied_preset"] = preset_key

        default_x = "price" if "price" in available_metrics else available_metrics[0]
        default_y = (
            "xpts_5gw"
            if "xpts_5gw" in available_metrics
            else next(key for key in available_metrics if key != default_x)
        )
        if st.session_state.get("matrix_x_axis") not in available_metrics:
            st.session_state["matrix_x_axis"] = default_x
        if st.session_state.get("matrix_y_axis") not in available_metrics:
            st.session_state["matrix_y_axis"] = default_y

        axis_columns = st.columns(2)
        x_key = axis_columns[0].selectbox(
            "X axis",
            available_metrics,
            format_func=lambda key: metric_definition(key).label,
            key="matrix_x_axis",
        )
        y_key = axis_columns[1].selectbox(
            "Y axis",
            available_metrics,
            format_func=lambda key: metric_definition(key).label,
            key="matrix_y_axis",
        )
        matching_preset = (
            MATRIX_PRESETS[preset_key]
            if preset_key != "custom"
            and MATRIX_PRESETS[preset_key].x_metric == x_key
            and MATRIX_PRESETS[preset_key].y_metric == y_key
            else None
        )
        if matching_preset:
            st.info(matching_preset.description)

        reference_columns = st.columns(3)
        reference_method = reference_columns[0].selectbox(
            "Reference lines",
            REFERENCE_METHODS,
            key="matrix_reference_method",
        )
        reference_position = None
        custom_x = custom_y = None
        if reference_method == "Position Median":
            reference_position = reference_columns[1].selectbox(
                "Reference position",
                sorted({record.position for record in matrix_records}),
                key="matrix_reference_position",
            )
        elif reference_method == "Custom":
            custom_x = reference_columns[1].number_input(
                "Custom X reference",
                value=float(
                    pd.Series(
                        [
                            value
                            for record in matrix_records
                            if (value := record.metric(x_key)) is not None
                        ]
                    ).median()
                ),
                key="matrix_custom_x",
            )
            custom_y = reference_columns[2].number_input(
                "Custom Y reference",
                value=float(
                    pd.Series(
                        [
                            value
                            for record in matrix_records
                            if (value := record.metric(y_key)) is not None
                        ]
                    ).median()
                ),
                key="matrix_custom_y",
            )

        encoding_columns = st.columns(4)
        color_mode = encoding_columns[0].selectbox(
            "Point color",
            ("None", "Position", "Team", "Risk category"),
            index=1,
            key="matrix_color_mode",
        )
        size_mode = encoding_columns[1].selectbox(
            "Point size",
            ("Fixed", "Price", "Ownership", "Blended xPts", "Optimization Score"),
            key="matrix_size_mode",
        )
        label_mode = encoding_columns[2].selectbox(
            "Player labels",
            ("Selected names", "Top N", "All names", "Hide names"),
            key="matrix_label_mode",
        )
        top_n = encoding_columns[3].number_input(
            "Top labels",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
            disabled=label_mode != "Top N",
            key="matrix_top_labels",
        )

        try:
            analysis = build_matrix(
                matrix_records,
                x_key,
                y_key,
                cast(ReferenceMethod, reference_method),
                custom_x=custom_x,
                custom_y=custom_y,
                reference_position=reference_position,
                labels=matching_preset.quadrant_labels if matching_preset else None,
                diagonal=matching_preset.diagonal if matching_preset else False,
            )
        except ValueError as error:
            st.warning(str(error))
        else:
            plotted_ids = {point.player_id for point in analysis.points}
            excluded_count = len(matrix_records) - len(analysis.points)
            st.plotly_chart(
                player_matrix_figure(
                    analysis,
                    color_mode=cast(ColorMode, color_mode),
                    size_mode=cast(SizeMode, size_mode),
                    label_mode=cast(LabelMode, label_mode),
                    highlighted_ids=frozenset(plotted_ids.intersection(selected_ids)),
                    top_n=int(top_n),
                ),
                width="stretch",
                config={"displaylogo": False, "responsive": True},
            )
            exclusion_note = (
                f" · {excluded_count} players omitted because an axis value is unavailable"
                if excluded_count
                else ""
            )
            diagonal_note = " · dotted line shows Market = Model" if analysis.diagonal else ""
            st.caption(
                f"Raw axes: **{analysis.x_metric.label}** ({analysis.x_metric.unit}) and "
                f"**{analysis.y_metric.label}** ({analysis.y_metric.unit}) · dashed references "
                f"use {analysis.reference_method}{diagonal_note}{exclusion_note}."
            )

            st.subheader("Quadrant insights")
            insight_columns = st.columns(2)
            for index, insight in enumerate(analysis.insights):
                with insight_columns[index % 2]:
                    st.markdown(f"#### {insight.label}")
                    if not insight.players:
                        st.caption("No players in this quadrant.")
                    for rank, point in enumerate(insight.players[:5], start=1):
                        score = (
                            f"score {point.optimization_score:.1f}"
                            if point.optimization_score is not None
                            else "score unavailable"
                        )
                        st.write(f"{rank}. **{point.full_name}** · {point.team} · {score}")

with forecast_tab:
    st.subheader("Future fixture and forecast comparison")
    if len(selected) < 2:
        st.info("Choose at least two players above to compare their future forecasts.")
    else:
        horizon = st.radio(
            "Forecast horizon",
            FORECAST_HORIZONS,
            index=2,
            format_func=lambda weeks: f"Next {weeks} GW" if weeks == 1 else f"Next {weeks} GWs",
            horizontal=True,
            key="analytics_forecast_horizon",
        )
        forecast_details = load_player_forecast_details(
            container, {record.player_id for record in selected}
        )
        comparison = build_forecast_comparison(selected, forecast_details, int(horizon))
        if len(comparison.series) < 2:
            st.info("Generate advanced forecasts to unlock future player comparisons.")
        else:
            st.subheader("Fixture comparison")
            fixture_frame = pd.DataFrame(fixture_comparison_rows(comparison))
            st.dataframe(fixture_frame, hide_index=True, width="stretch")
            st.caption(
                "A = attacking difficulty from the opponent's defensive strength; D = defensive "
                "difficulty from the opponent's attacking strength. Ratings use the current "
                "official FPL team-strength universe: 1 is easier and 5 is harder."
            )

            chart_mode = st.radio(
                "Forecast view",
                ("Weekly xPts", "Cumulative xPts"),
                horizontal=True,
                key="analytics_forecast_chart_mode",
            )
            st.plotly_chart(
                player_forecast_figure(comparison, cast(ForecastChartMode, chart_mode)),
                width="stretch",
                config={"displaylogo": False, "responsive": True},
            )
            horizon_label = "–".join(comparison.gameweeks)
            freshness = (
                format_timestamp(comparison.forecasted_at)
                if comparison.forecasted_at is not None
                else "unknown"
            )
            st.caption(
                f"Raw blended expected points · horizon **{horizon_label}** · comparison universe "
                f"**{len(comparison.series)} selected players** · forecast updated "
                f"**{freshness}**. "
                "Hover for statistical, market, minutes, opponent, and confidence details."
            )
            forecast_frame = pd.DataFrame(forecast_export_rows(comparison))
            st.download_button(
                "Download forecast comparison (CSV)",
                forecast_frame.to_csv(index=False),
                file_name="fpl-forecast-comparison.csv",
                mime="text/csv",
                key="analytics_forecast_csv",
            )
