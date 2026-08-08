"""Component-level six-Gameweek statistical forecast explorer."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from shared import market_weight, page_setup

from fpl_optimizer.database.forecast_repository import ForecastRepository

container = page_setup("Forecasts", "📈")
st.title("Advanced forecasts")
st.caption("2026/27 scoring, defensive contributions, improved minutes, and optional markets")
market_status = container.live_odds.status()
if market_status.last_sync is not None:
    label = "STALE ODDS" if market_status.stale else "Market data current"
    st.caption(f"{label} · odds updated {market_status.last_sync:%d %b, %H:%M}")
else:
    st.caption("Market forecast unavailable · using statistical forecast only")

with container.database.session() as session:
    repository = ForecastRepository(session)
    choices = repository.player_choices()
    latest = repository.latest_prediction_at()

if latest is None:
    st.info("Generate statistical forecasts from the sidebar to explore player projections.")
elif choices:
    labels = {player_id: f"{name} · {team}" for player_id, name, team in choices}
    selected_id = st.selectbox(
        "Player",
        options=list(labels),
        format_func=lambda player_id: labels[player_id],
    )
    with container.database.session() as session:
        details = ForecastRepository(session).player_details(selected_id, market_weight())

    if details:
        first = details[0]
        cols = st.columns(4)
        cols[0].metric("Next GW blended xPts", f"{float(first['Blended xPts']):.1f}")
        cols[1].metric("Expected minutes", f"{float(first['Expected minutes']):.0f}")
        cols[2].metric("Next 3", f"{sum(float(row['Blended xPts']) for row in details[:3]):.1f}")
        cols[3].metric("Next 6", f"{sum(float(row['Blended xPts']) for row in details[:6]):.1f}")

        display_columns = [
            "Gameweek",
            "Opponent",
            "Fixtures",
            "Expected minutes",
            "Appearance",
            "Goals",
            "Assists",
            "Clean sheet",
            "Saves",
            "Bonus",
            "Defensive contribution",
            "Deductions",
            "Stat xPts",
            "Market xPts",
            "Goalscorer probability",
            "Blended xPts",
            "Market edge",
            "Confidence",
        ]
        frame = pd.DataFrame(details)[display_columns]
        frame["Goalscorer probability"] = frame["Goalscorer probability"] * 100
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={
                column: st.column_config.NumberColumn(column, format="%.1f")
                for column in display_columns[3:-1]
            }
            | {
                "Goalscorer probability": st.column_config.NumberColumn(format="%.1f%%")
            },
        )

        with st.expander("Why this projection?"):
            explanation = first["Explanation"]
            st.write(
                f"Start probability: **{float(explanation['p_start']):.0%}** · "
                f"60+ probability: **{float(explanation['p_60_plus']):.0%}** · "
                f"Availability: **{float(explanation['availability']):.0%}**"
            )
            fixtures = explanation.get("fixtures", [])
            if fixtures:
                st.dataframe(pd.DataFrame(fixtures).round(2), hide_index=True, width="stretch")
            else:
                st.write("This is a blank Gameweek, so projected points and minutes are zero.")
            st.caption(str(explanation["limitations"]))
            market_explanation = first.get("Market explanation")
            if market_explanation:
                st.subheader("Market model")
                st.dataframe(
                    pd.DataFrame(market_explanation["fixtures"]).round(2),
                    hide_index=True,
                    width="stretch",
                )
                st.caption(str(market_explanation["limitations"]))
