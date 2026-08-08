"""Initial legal 15-player squad optimizer."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st
from shared import active_strategy_profile, market_weight, page_setup

from fpl_optimizer.domain.optimizer import SquadOptimizationRequest
from fpl_optimizer.optimizer.squad import MAX_PER_TEAM, POSITION_LIMITS

container = page_setup("Optimizer", "🧮")
st.title("Initial squad optimizer")
st.caption("Build the highest-utility legal 15-player squad for your active strategy")

profile = active_strategy_profile()
blend = market_weight()
context_cols = st.columns(4)
context_cols[0].metric("Strategy", profile.preset)
context_cols[1].metric("Mode", profile.mode.title())
context_cols[2].metric("Planning horizon", f"{profile.horizon} GW")
context_cols[3].metric("Market influence", f"{blend:.0%}")
st.caption("Change strategy preferences on Strategy and forecast blending in the sidebar.")

scores = container.strategy.score(profile, blend)
if not scores:
    st.warning("Generate statistical forecasts before optimizing an initial squad.")
    st.stop()

labels = {
    score.player_id: (
        f"{score.player} · {score.position} · {score.team} · £{score.price:.1f}m · "
        f"score {score.score:.1f}"
    )
    for score in scores
}

st.subheader("Squad constraints")
control_cols = st.columns([1, 2, 2])
budget = control_cols[0].number_input(
    "Available budget",
    min_value=50.0,
    max_value=150.0,
    value=100.0,
    step=0.5,
    format="%.1f",
    help="Total purchase-price budget in millions.",
)
locked = control_cols[1].multiselect(
    "Lock / must buy",
    options=list(labels),
    format_func=lambda player_id: labels[player_id],
    help="Every selected player must appear in the optimized squad.",
)
excluded = control_cols[2].multiselect(
    "Exclude",
    options=list(labels),
    format_func=lambda player_id: labels[player_id],
    help="Selected players cannot appear in the optimized squad.",
)

request = SquadOptimizationRequest(
    budget=budget,
    locked_player_ids=tuple(locked),
    excluded_player_ids=tuple(excluded),
)
signature = (asdict(profile), blend, asdict(request))

if st.button("Optimize 15-player squad", type="primary"):
    try:
        with st.spinner("Solving the legal squad integer program…"):
            report = container.optimizer.run(profile, blend, request)
        st.session_state["squad_optimizer_result"] = {
            "signature": signature,
            "report": report,
        }
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("squad_optimizer_result")
if isinstance(stored, dict) and stored.get("signature") == signature:
    report = stored["report"]
    result = report.result
    st.success(f"Optimal legal squad found · run #{report.run_id} · {result.solver}")
    summary_cols = st.columns(6)
    summary_cols[0].metric("Squad cost", f"£{result.total_cost:.1f}m")
    summary_cols[1].metric("Remaining", f"£{result.budget_remaining:.1f}m")
    summary_cols[2].metric(f"{profile.horizon}GW xPts", f"{result.total_xpts:.1f}")
    summary_cols[3].metric("Strategy objective", f"{result.objective_score:.1f}")
    summary_cols[4].metric("Avg ownership", f"{result.average_ownership:.1f}%")
    summary_cols[5].metric("Avg risk", f"{result.average_risk:.1f}/100")

    squad = pd.DataFrame(
        [
            {
                "Player": player.player,
                "Position": player.position,
                "Team": player.team,
                "Price": player.price,
                f"{profile.horizon}GW xPts": player.horizon_xpts,
                "Optimization Score": player.optimization_score,
                "Ownership %": player.ownership,
                "Risk": player.risk,
                "Locked": player.locked,
            }
            for player in result.players
        ]
    )
    st.dataframe(
        squad,
        hide_index=True,
        width="stretch",
        column_config={
            "Price": st.column_config.NumberColumn(format="£%.1fm"),
            f"{profile.horizon}GW xPts": st.column_config.NumberColumn(format="%.1f"),
            "Optimization Score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f"
            ),
            "Ownership %": st.column_config.NumberColumn(format="%.1f%%"),
            "Risk": st.column_config.NumberColumn(format="%.1f/100"),
        },
    )

    st.subheader("Constraint audit")
    team_counts = squad.groupby("Team").size()
    audit_cols = st.columns(4)
    audit_cols[0].success(f"15 players: {len(squad)}")
    audit_cols[1].success(
        "Positions: "
        + " · ".join(
            f"{position} {int((squad['Position'] == position).sum())}/{required}"
            for position, required in POSITION_LIMITS.items()
        )
    )
    audit_cols[2].success(f"Club cap: {int(team_counts.max())}/{MAX_PER_TEAM}")
    audit_cols[3].success(f"Budget: £{result.total_cost:.1f}m/£{result.budget:.1f}m")
    st.info(
        "To manage this squad and generate its formation, captain, vice-captain, and bench order, "
        "open My Team and choose Use latest optimized squad."
    )
elif stored is not None:
    st.info("Constraints or strategy changed. Optimize again to refresh the squad.")

recent = container.optimizer.recent()
if recent:
    with st.expander(f"Recent optimization runs ({len(recent)})"):
        st.dataframe(
            pd.DataFrame(recent),
            hide_index=True,
            width="stretch",
            column_config={
                "Budget": st.column_config.NumberColumn(format="£%.1fm"),
                "Cost": st.column_config.NumberColumn(format="£%.1fm"),
                "Objective": st.column_config.NumberColumn(format="%.1f"),
                "Projected xPts": st.column_config.NumberColumn(format="%.1f"),
            },
        )
