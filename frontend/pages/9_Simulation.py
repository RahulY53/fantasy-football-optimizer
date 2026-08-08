"""Current-team Monte Carlo simulation workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from shared import market_weight, page_setup

container = page_setup("Simulation", "🎲")
st.title("Monte Carlo simulation")
st.caption("Explore ranges, downside risk, and haul probabilities beyond average xPts")

team = container.team.get()
if team is None:
    st.info("Save your 15-player squad on **My Team** before running a simulation.")
    st.stop()

blend = market_weight()
context_cols = st.columns(3)
context_cols[0].metric("Current squad", len(team.players))
context_cols[1].metric("Market influence", f"{blend:.0%}")
context_cols[2].metric("Scenario", "Hold current squad")

control_cols = st.columns(3)
horizon = control_cols[0].slider(
    "Simulation horizon", min_value=1, max_value=6, value=3, format="%d Gameweeks"
)
iterations = control_cols[1].select_slider(
    "Iterations",
    options=[1_000, 2_500, 5_000, 10_000, 25_000, 50_000],
    value=10_000,
    format_func=lambda value: f"{value:,}",
)
seed = int(
    control_cols[2].number_input(
        "Random seed",
        min_value=0,
        max_value=2_147_483_647,
        value=42,
        step=1,
        help="Use the same seed to reproduce exactly the same draws.",
    )
)
team_signature = tuple(
    (player.player_id, player.purchase_price, player.selling_price) for player in team.players
)
signature = (team_signature, horizon, iterations, seed, blend)

if st.button("Run simulation", type="primary"):
    try:
        with st.spinner(f"Simulating {iterations:,} possible outcomes…"):
            report = container.simulation.run(
                horizon=horizon,
                iterations=iterations,
                seed=seed,
                market_weight=blend,
            )
        st.session_state["simulation_result"] = {
            "signature": signature,
            "report": report,
        }
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("simulation_result")
if isinstance(stored, dict) and stored.get("signature") == signature:
    report = stored["report"]
    result = report.result
    st.success(
        f"Completed {result.iterations:,} reproducible simulations · run #{report.run_id}"
    )
    summary_cols = st.columns(6)
    summary_cols[0].metric("Mean", f"{result.mean:.1f}")
    summary_cols[1].metric("Median", f"{result.median:.1f}")
    summary_cols[2].metric("P10 downside", f"{result.p10:.1f}")
    summary_cols[3].metric("P90 upside", f"{result.p90:.1f}")
    summary_cols[4].metric("50/GW or better", f"{result.probability_50_per_gw_plus:.1%}")
    summary_cols[5].metric("60/GW or better", f"{result.probability_60_per_gw_plus:.1%}")

    st.subheader("Total-points distribution")
    histogram = pd.DataFrame(
        [
            {
                "Points": (bucket.lower + bucket.upper) / 2,
                "Outcomes": bucket.count,
            }
            for bucket in result.histogram
        ]
    ).set_index("Points")
    st.bar_chart(histogram, y="Outcomes")
    st.caption(
        f"Middle 50%: {result.p25:.1f}–{result.p75:.1f} · standard deviation "
        f"{result.standard_deviation:.1f} · below 40/GW "
        f"{result.probability_below_40_per_gw:.1%}"
    )

    st.subheader("Gameweek ranges")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Gameweek": week.gameweek,
                    "Formation": week.formation,
                    "Captain": week.captain,
                    "Expected xPts": week.expected_points,
                    "Simulation mean": week.mean,
                    "Median": week.median,
                    "P10": week.p10,
                    "P90": week.p90,
                    "40+ probability": week.probability_40_plus * 100,
                }
                for week in result.weeks
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            column: st.column_config.NumberColumn(format="%.1f")
            for column in ("Expected xPts", "Simulation mean", "Median", "P10", "P90")
        }
        | {"40+ probability": st.column_config.NumberColumn(format="%.1f%%")},
    )

    st.subheader("Player outcome ranges")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Player": player.player,
                    "Position": player.position,
                    "Team": player.team,
                    "Selected GWs": player.selected_gameweeks,
                    "Captained GWs": player.captained_gameweeks,
                    "Mean": player.mean,
                    "P10": player.p10,
                    "P90": player.p90,
                    "Blank probability": player.blank_probability * 100,
                    "Return probability": player.return_probability * 100,
                    "Haul probability": player.haul_probability * 100,
                }
                for player in result.players
            ]
        ).sort_values("Mean", ascending=False),
        hide_index=True,
        width="stretch",
        column_config={
            column: st.column_config.NumberColumn(format="%.1f%%")
            for column in ("Blank probability", "Return probability", "Haul probability")
        },
    )

    st.info(
        "The selected XI and captain maximize expected xPts before the draws. Same-club attacking "
        "and clean-sheet outcomes share shocks, so stacking players changes both upside and risk."
    )
    st.caption(
        "This baseline holds the current squad, ignores autosubs and chips, and approximates "
        "bonus, saves, cards, and double-Gameweek dependence. It is a decision aid, not a "
        "calibrated probability guarantee."
    )
elif stored is not None:
    st.info("Simulation controls or team changed. Run again to refresh the distributions.")

recent = container.simulation.recent()
if recent:
    with st.expander(f"Recent simulation runs ({len(recent)})"):
        recent_frame = pd.DataFrame(recent)
        recent_frame["Market influence"] = recent_frame["Market influence"] * 100
        st.dataframe(
            recent_frame,
            hide_index=True,
            width="stretch",
            column_config={
                "Market influence": st.column_config.NumberColumn(format="%.0f%%"),
                **{
                    column: st.column_config.NumberColumn(format="%.1f")
                    for column in ("Mean", "Median", "P10", "P90")
                },
            },
        )
