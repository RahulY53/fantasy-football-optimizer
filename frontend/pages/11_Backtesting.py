"""Historical forecast backtesting and blend calibration workspace."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st
from shared import page_setup

container = page_setup("Backtesting", "🧪")
st.title("Backtesting and calibration")
st.caption("Measure how pre-deadline forecasts performed against final FPL outcomes")

outcome_count = container.backtesting.outcome_count()
summary_cols = st.columns(3)
summary_cols[0].metric("Historical outcomes", f"{outcome_count:,}")
summary_cols[1].metric("Evaluation", "Chronological")
summary_cols[2].metric("Live settings", "Never auto-changed")

st.subheader("1. Import final outcomes")
st.write(
    "Upload one row per official FPL player and Gameweek. Existing rows are updated only after "
    "the whole file validates successfully."
)
template = (
    "player_id,gameweek,actual_points,actual_minutes,goals,assists,clean_sheets,"
    "saves,bonus,finalized_at\n"
    "1,1,6,90,0,1,0,0,1,2026-08-18T23:00:00Z\n"
)
st.download_button(
    "Download CSV template",
    data=template,
    file_name="fpl_historical_outcomes.csv",
    mime="text/csv",
)
upload = st.file_uploader("Historical outcomes CSV", type=["csv"])
if upload is not None and st.button("Import outcomes", type="primary"):
    try:
        imported = container.backtesting.import_csv(
            upload.getvalue().decode("utf-8-sig"), upload.name
        )
        st.success(f"Imported {imported:,} player-Gameweek outcomes.")
        st.rerun()
    except (UnicodeDecodeError, ValueError) as error:
        st.error(str(error))

st.subheader("2. Evaluate historical forecasts")
st.write(
    "Only forecasts whose prediction and input cutoff were both at or before that Gameweek's "
    "deadline are eligible. With four or more Gameweeks, earlier weeks select the blend and later "
    "weeks provide a holdout evaluation."
)
if st.button("Run backtest", type="primary", disabled=outcome_count == 0):
    try:
        with st.spinner("Matching pre-deadline forecasts and evaluating blend weights…"):
            report = container.backtesting.run()
        st.session_state["backtest_report"] = report
    except ValueError as error:
        st.error(str(error))

report = st.session_state.get("backtest_report")
if report is not None:
    result = report.result
    st.success(
        f"Suggested market influence: {result.selected_market_weight:.0%} "
        f"({result.evaluation_mode}; advisory only)"
    )
    for warning in result.warnings:
        st.warning(warning)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Matched forecasts", f"{result.observations:,}")
    metric_cols[1].metric("Gameweeks", result.gameweeks)
    metric_cols[2].metric("Stat RMSE", f"{result.statistical.rmse:.2f} pts")
    delta = result.selected_blend.rmse - result.statistical.rmse
    metric_cols[3].metric(
        "Selected blend RMSE",
        f"{result.selected_blend.rmse:.2f} pts",
        delta=f"{delta:+.2f} vs stat",
        delta_color="inverse",
    )

    st.caption(
        f"Calibration: {', '.join(result.calibration_gameweeks)} · "
        f"Evaluation: {', '.join(result.evaluation_gameweeks)}"
    )
    comparisons = [
        {"Forecast": "Statistical", **asdict(result.statistical)},
        {"Forecast": "Selected blend", **asdict(result.selected_blend)},
    ]
    if result.market is not None:
        comparisons.insert(1, {"Forecast": "Market (covered only)", **asdict(result.market)})
    st.subheader("Accuracy comparison")
    st.dataframe(
        pd.DataFrame(comparisons).rename(
            columns={
                "samples": "Samples",
                "mae": "MAE",
                "rmse": "RMSE",
                "bias": "Bias",
                "correlation": "Correlation",
            }
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Samples": st.column_config.NumberColumn(format="%d"),
            "MAE": st.column_config.NumberColumn(format="%.2f"),
            "RMSE": st.column_config.NumberColumn(format="%.2f"),
            "Bias": st.column_config.NumberColumn(format="%+.2f"),
            "Correlation": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    weights = pd.DataFrame(
        [
            {
                "Market influence": row.market_weight * 100,
                "Calibration RMSE": row.calibration_rmse,
                "Evaluation RMSE": row.metrics.rmse,
            }
            for row in result.weights
        ]
    ).set_index("Market influence")
    st.subheader("Blend-weight curve")
    st.line_chart(weights)
    st.caption("Horizontal axis is market influence in percent; lower RMSE is better.")

    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.subheader("By position")
        st.dataframe(
            pd.DataFrame(
                [{"Position": row.position, **asdict(row.metrics)} for row in result.positions]
            ).rename(
                columns={
                    "samples": "Samples",
                    "mae": "MAE",
                    "rmse": "RMSE",
                    "bias": "Bias",
                    "correlation": "Correlation",
                }
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Samples": st.column_config.NumberColumn(format="%d"),
                "MAE": st.column_config.NumberColumn(format="%.2f"),
                "RMSE": st.column_config.NumberColumn(format="%.2f"),
                "Bias": st.column_config.NumberColumn(format="%+.2f"),
                "Correlation": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    with detail_cols[1]:
        st.subheader("Calibration bands")
        st.dataframe(
            pd.DataFrame([asdict(row) for row in result.calibration_bands]).rename(
                columns={
                    "label": "Predicted xPts",
                    "samples": "Samples",
                    "mean_prediction": "Mean predicted",
                    "mean_actual": "Mean actual",
                    "bias": "Bias",
                }
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Samples": st.column_config.NumberColumn(format="%d"),
                "Mean predicted": st.column_config.NumberColumn(format="%.2f"),
                "Mean actual": st.column_config.NumberColumn(format="%.2f"),
                "Bias": st.column_config.NumberColumn(format="%+.2f"),
            },
        )

    if result.expected_minutes is not None:
        minutes = result.expected_minutes
        st.subheader("Expected-minutes accuracy")
        minutes_cols = st.columns(4)
        minutes_cols[0].metric("Samples", minutes.samples)
        minutes_cols[1].metric("MAE", f"{minutes.mae:.1f} min")
        minutes_cols[2].metric("RMSE", f"{minutes.rmse:.1f} min")
        minutes_cols[3].metric("Bias", f"{minutes.bias:+.1f} min")

    st.info(
        "The suggested weight is evidence for review, not an automatic setting change. Check "
        "sample size, holdout performance, position errors, and calibration bands before acting."
    )

recent = container.backtesting.recent()
if recent:
    with st.expander(f"Recent backtests ({len(recent)})"):
        frame = pd.DataFrame(recent)
        frame["Suggested market influence"] *= 100
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={
                "Suggested market influence": st.column_config.NumberColumn(format="%.0f%%"),
                "Stat RMSE": st.column_config.NumberColumn(format="%.2f"),
                "Blend RMSE": st.column_config.NumberColumn(format="%.2f"),
            },
        )
