"""Joint multi-Gameweek transfer and lineup planner."""

from __future__ import annotations

from dataclasses import asdict, replace

import pandas as pd
import streamlit as st
from shared import active_strategy_profile, market_weight, page_setup

container = page_setup("Planner", "🗓️")
st.title("Multi-Gameweek planner")
st.caption("Optimize transfers, starting XIs, and captains as one connected future path")

team = container.team.get()
if team is None:
    st.info("Save your 15-player squad on **My Team** before generating a plan.")
    st.stop()

base_profile = active_strategy_profile()
blend = market_weight()
context_cols = st.columns(4)
context_cols[0].metric("Starting bank", f"£{team.bank:.1f}m")
context_cols[1].metric("Free transfers", team.free_transfers)
context_cols[2].metric("Strategy", base_profile.preset)
context_cols[3].metric("Market influence", f"{blend:.0%}")

horizon = st.slider(
    "Planning horizon",
    min_value=2,
    max_value=6,
    value=max(2, base_profile.horizon),
    format="%d Gameweeks",
    help="Every week is optimized jointly, so a move can be delayed for a later fixture swing.",
)
profile = replace(base_profile, horizon=horizon)
team_signature = (
    tuple((p.player_id, p.purchase_price, p.selling_price) for p in team.players),
    team.bank,
    team.free_transfers,
)
signature = (team_signature, asdict(profile), blend)

if st.button("Build multi-Gameweek plan", type="primary"):
    try:
        with st.spinner("Solving the connected transfer and lineup path…"):
            report = container.planner.run(profile, blend, horizon)
        st.session_state["multi_gameweek_plan"] = {
            "signature": signature,
            "report": report,
        }
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("multi_gameweek_plan")
if isinstance(stored, dict) and stored.get("signature") == signature:
    report = stored["report"]
    plan = report.plan
    st.success(f"Optimal {plan.horizon}-Gameweek path found · run #{report.run_id}")
    summary_cols = st.columns(5)
    summary_cols[0].metric("Net projected points", f"{plan.net_projected_points:.1f}")
    summary_cols[1].metric("Gross projected points", f"{plan.gross_projected_points:.1f}")
    summary_cols[2].metric("Transfers", plan.total_transfers)
    summary_cols[3].metric("Hit cost", f"-{plan.total_hits} pts")
    summary_cols[4].metric("Solver", "HiGHS MILP")

    overview = pd.DataFrame(
        [
            {
                "Gameweek": week.gameweek,
                "Transfers": len(week.transfers),
                "Free transfers before": week.free_transfers_before,
                "Hit": week.hit_cost,
                "Bank after": week.bank_after,
                "Formation": week.formation,
                "Captain": week.captain,
                "Gross xPts": week.projected_points,
                "Net xPts": week.net_projected_points,
            }
            for week in plan.weeks
        ]
    )
    st.subheader("Plan overview")
    st.dataframe(
        overview,
        hide_index=True,
        width="stretch",
        column_config={
            "Hit": st.column_config.NumberColumn(format="-%d pts"),
            "Bank after": st.column_config.NumberColumn(format="£%.1fm"),
            "Gross xPts": st.column_config.NumberColumn(format="%.1f"),
            "Net xPts": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    score_names = {
        score.player_id: f"{score.player} ({score.position}, {score.team})"
        for score in container.strategy.score(profile, blend)
    }
    st.subheader("Week-by-week decisions")
    for week in plan.weeks:
        label = (
            f"{week.gameweek} · {len(week.transfers)} transfer(s) · "
            f"{week.net_projected_points:.1f} net xPts"
        )
        with st.expander(label, expanded=week == plan.weeks[0]):
            detail_cols = st.columns(4)
            detail_cols[0].metric("Formation", week.formation)
            detail_cols[1].metric("Captain", week.captain)
            detail_cols[2].metric(
                "Free transfers", f"{week.free_transfers_before} → {week.free_transfers_after}"
            )
            detail_cols[3].metric("Bank after", f"£{week.bank_after:.1f}m")
            if week.transfers:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Position": move.position,
                                "OUT": move.out_player,
                                "Sell": move.selling_price,
                                "IN": move.in_player,
                                "Buy": move.buy_price,
                                "Bank change": move.bank_change,
                            }
                            for move in week.transfers
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Sell": st.column_config.NumberColumn(format="£%.1fm"),
                        "Buy": st.column_config.NumberColumn(format="£%.1fm"),
                        "Bank change": st.column_config.NumberColumn(format="%+.1fm"),
                    },
                )
            else:
                st.write("Roll the transfer and keep the squad unchanged.")
            st.write("**Starting XI:** " + " · ".join(score_names[p] for p in week.starter_ids))
            st.caption(
                f"XI {week.lineup_xpts:.1f} + captain {week.captain_xpts:.1f} "
                f"- hit {week.hit_cost} = {week.net_projected_points:.1f} projected points"
            )

    st.info(
        "This is one joint optimization: later fixture gains can justify delaying a move, rolling "
        "a transfer, or taking a hit. Re-run it after each deadline because forecasts and prices "
        "will change."
    )
    st.caption(
        "Phase 8 uses static current prices, permits at most two transfers per Gameweek, and does "
        "not yet model chips, uncertainty scenarios, or price-change forecasts. It searches all "
        "current players plus the strongest 35 forecast alternatives per position."
    )
elif stored is not None:
    st.info("Team, strategy, or horizon changed. Build the plan again to refresh it.")

recent = container.planner.recent()
if recent:
    with st.expander(f"Recent multi-Gameweek plans ({len(recent)})"):
        st.dataframe(
            pd.DataFrame(recent),
            hide_index=True,
            width="stretch",
            column_config={
                "Starting bank": st.column_config.NumberColumn(format="£%.1fm"),
                "Net projected points": st.column_config.NumberColumn(format="%.1f"),
            },
        )
