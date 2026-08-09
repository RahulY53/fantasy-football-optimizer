"""Advanced read-only model inspection workspace."""

from __future__ import annotations

from dataclasses import asdict
from statistics import mean, median

import pandas as pd
import plotly.express as px
import streamlit as st
from shared import active_strategy_profile, format_timestamp, page_setup

container = page_setup("Model Lab", "🔬")
st.title("Model Lab")
st.caption("Advanced diagnostics for the cached forecasting and strategy pipeline")
st.info(
    "This is an inspection workspace for advanced users. Lab controls only recombine stored "
    "values; they do not generate forecasts, run an optimizer, or change your active settings."
)

lab_weight = st.slider(
    "Lab market influence",
    min_value=0,
    max_value=100,
    value=int(st.session_state.get("market_influence", 30)),
    step=5,
    key="model_lab_market_influence",
    help="A temporary what-if blend used only on this page.",
) / 100.0
report = container.model_lab.report(active_strategy_profile(), lab_weight)
rows = list(report.diagnostics)
covered = [row for row in rows if row.market_xpts is not None]

metrics = st.columns(5)
metrics[0].metric("Players", len(rows))
metrics[1].metric("Market coverage", f"{len(covered) / len(rows):.0%}" if rows else "—")
metrics[2].metric(
    "Mean expected minutes", f"{mean(row.expected_minutes for row in rows):.1f}" if rows else "—"
)
metrics[3].metric("Model versions", len(report.versions))
metrics[4].metric("Backtest runs", len(report.recent_backtests))

if report.forecast_at:
    st.caption(f"Statistical forecast: {format_timestamp(report.forecast_at)}")
else:
    st.warning("No cached statistical forecasts exist yet. Generate forecasts from the sidebar.")

overview_tab, blend_tab, minutes_tab, market_tab, calibration_tab, features_tab, versions_tab = (
    st.tabs(
        [
            "Overview",
            "Blend lab",
            "Minutes model",
            "Market model",
            "Calibration",
            "Feature influence",
            "Versions & settings",
        ]
    )
)

diagnostic_frame = pd.DataFrame(
    [
        {
            "Player": row.player,
            "Team": row.team,
            "Pos": row.position,
            "Gameweek": row.gameweek,
            "Opponent": row.opponent,
            "xMin": row.expected_minutes,
            "Start %": row.start_probability * 100,
            "Stat xPts": row.stat_xpts,
            "Market xPts": row.market_xpts,
            "Blend xPts": row.blended_xpts,
            "Market edge": row.market_edge,
            "Confidence": row.confidence,
            "Model": row.model_version,
        }
        for row in rows
    ]
)

with overview_tab:
    st.subheader("Pipeline snapshot")
    st.write(
        "The statistical model estimates minutes and scoring components first. Independent "
        "market xPts are then blended where coverage exists; the strategy layer applies your "
        "preferences after forecasting."
    )
    if rows:
        st.dataframe(
            diagnostic_frame.sort_values("Blend xPts", ascending=False).head(25),
            hide_index=True,
            width="stretch",
            column_config={
                "xMin": st.column_config.NumberColumn(format="%.1f"),
                "Start %": st.column_config.NumberColumn(format="%.0f%%"),
                "Stat xPts": st.column_config.NumberColumn(format="%.2f"),
                "Market xPts": st.column_config.NumberColumn(format="%.2f"),
                "Blend xPts": st.column_config.NumberColumn(format="%.2f"),
                "Market edge": st.column_config.NumberColumn(format="%+.2f"),
            },
        )
        st.download_button(
            "Export model diagnostics",
            diagnostic_frame.to_csv(index=False).encode("utf-8"),
            "fpl_model_lab_diagnostics.csv",
            "text/csv",
        )

with blend_tab:
    st.subheader(f"Temporary blend: {lab_weight:.0%} market")
    if covered:
        avg_change = mean(row.blended_xpts - row.stat_xpts for row in covered)
        cols = st.columns(3)
        cols[0].metric("Covered players", len(covered))
        cols[1].metric("Mean blend shift", f"{avg_change:+.2f} pts")
        cols[2].metric(
            "Largest disagreement", f"{max(abs(row.market_edge or 0) for row in covered):.2f} pts"
        )
        blend_frame = diagnostic_frame.dropna(subset=["Market xPts"]).sort_values(
            "Market edge", key=lambda series: series.abs(), ascending=False
        )
        st.plotly_chart(
            px.scatter(
                blend_frame,
                x="Stat xPts",
                y="Market xPts",
                color="Pos",
                hover_name="Player",
                title="Statistical versus market xPts",
            ),
            width="stretch",
        )
        st.dataframe(blend_frame.head(30), hide_index=True, width="stretch")
    else:
        st.info("No cached player-level market forecasts are available for comparison.")

with minutes_tab:
    st.subheader("Expected-minutes diagnostics")
    if rows:
        cols = st.columns(4)
        cols[0].metric("Median xMin", f"{median(row.expected_minutes for row in rows):.1f}")
        cols[1].metric("60+ xMin", sum(row.expected_minutes >= 60 for row in rows))
        cols[2].metric("Below 30 xMin", sum(row.expected_minutes < 30 for row in rows))
        cols[3].metric("High confidence", sum(row.confidence == "High" for row in rows))
        minute_frame = diagnostic_frame[
            ["Player", "Team", "Pos", "xMin", "Start %", "Confidence"]
        ].sort_values("xMin", ascending=False)
        st.plotly_chart(
            px.bar(
                minute_frame.head(30),
                x="Player",
                y="xMin",
                color="Pos",
                title="Top 30 expected-minutes projections",
            ),
            width="stretch",
        )
        st.dataframe(minute_frame, hide_index=True, width="stretch")

with market_tab:
    st.subheader("Market coverage and disagreement")
    if covered:
        edge_rows = sorted(covered, key=lambda row: abs(row.market_edge or 0), reverse=True)
        st.write(
            f"{len(covered):,} of {len(rows):,} first-horizon player forecasts have matching "
            "market projections. Missing market values fall back to statistical xPts."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Player": [row.player for row in edge_rows],
                    "Team": [row.team for row in edge_rows],
                    "Stat xPts": [row.stat_xpts for row in edge_rows],
                    "Market xPts": [row.market_xpts for row in edge_rows],
                    "Edge": [row.market_edge for row in edge_rows],
                }
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Refresh live odds and regenerate market forecasts to populate this view.")

with calibration_tab:
    st.subheader("Latest leakage-safe backtest")
    latest = report.latest_backtest
    if latest:
        statistical = latest.get("statistical", {})
        selected = latest.get("selected_blend", {})
        if isinstance(statistical, dict) and isinstance(selected, dict):
            cols = st.columns(4)
            cols[0].metric("Observations", latest.get("observations", 0))
            cols[1].metric("Gameweeks", latest.get("gameweeks", 0))
            cols[2].metric("Stat RMSE", f"{float(statistical.get('rmse', 0)):.2f}")
            cols[3].metric("Blend RMSE", f"{float(selected.get('rmse', 0)):.2f}")
        bands = latest.get("calibration_bands", [])
        if isinstance(bands, list) and bands:
            st.dataframe(pd.DataFrame(bands), hide_index=True, width="stretch")
        st.caption(
            "Backtests only match forecasts whose prediction and input cutoff predate the "
            "official Gameweek deadline. Results remain advisory."
        )
    else:
        st.info("Run a historical evaluation on Backtesting to populate calibration diagnostics.")
    if report.recent_backtests:
        with st.expander("Recent backtest runs"):
            st.dataframe(pd.DataFrame(report.recent_backtests), hide_index=True, width="stretch")

with features_tab:
    st.subheader(f"Strategy feature influence · {active_strategy_profile().preset}")
    st.caption(
        "Mean contribution across players after percentile normalization. This explains the "
        "ranking layer, not causal importance in the statistical forecast."
    )
    if report.feature_influence:
        feature_frame = pd.DataFrame([asdict(row) for row in report.feature_influence]).rename(
            columns={
                "label": "Feature",
                "raw_weight": "Raw weight",
                "normalized_weight": "Normalized weight",
                "mean_contribution": "Mean score contribution",
                "top_player": "Highest player",
                "top_contribution": "Highest contribution",
            }
        )
        st.plotly_chart(
            px.bar(
                feature_frame,
                x="Feature",
                y="Mean score contribution",
                title="Mean contribution to strategy score",
            ),
            width="stretch",
        )
        st.dataframe(
            feature_frame.drop(columns=["feature"]), hide_index=True, width="stretch"
        )
    else:
        st.info("Cached forecasts are required to inspect strategy feature influence.")

with versions_tab:
    st.subheader("Safe runtime settings")
    st.dataframe(
        pd.DataFrame(report.safe_settings, columns=["Setting", "Value"]),
        hide_index=True,
        width="stretch",
    )
    st.caption("Secrets, URLs, local paths, and credential values are deliberately excluded.")
    st.subheader("Immutable model versions")
    if report.versions:
        version_frame = pd.DataFrame(
            [
                {
                    "Name": row.name,
                    "Version": row.semantic_version,
                    "Feature schema": row.feature_schema,
                    "Code revision": row.code_revision,
                    "Created": row.created_at,
                    "Forecast rows": row.forecast_rows,
                }
                for row in report.versions
            ]
        )
        st.dataframe(version_frame, hide_index=True, width="stretch")
        for version in report.versions:
            with st.expander(f"{version.name} {version.semantic_version} parameters"):
                st.dataframe(
                    pd.DataFrame(version.parameters, columns=["Parameter", "Value"]),
                    hide_index=True,
                    width="stretch",
                )
    else:
        st.info("No model version metadata has been saved yet.")
