"""Wildcard, Free Hit, Bench Boost, and Triple Captain workspace."""

from __future__ import annotations

from dataclasses import asdict, replace

import pandas as pd
import streamlit as st
from shared import active_strategy_profile, market_weight, page_setup

container = page_setup("Chips", "🃏")
st.title("Chip planner")
st.caption("Compare the best modeled use of each currently available chip")

team = container.team.get()
if team is None:
    st.info("Save your 15-player squad on **My Team** before evaluating chips.")
    st.stop()

base_profile = active_strategy_profile()
blend = market_weight()
available = [
    name
    for name, value in (
        ("Wildcard", team.wildcard_available),
        ("Free Hit", team.free_hit_available),
        ("Bench Boost", team.bench_boost_available),
        ("Triple Captain", team.triple_captain_available),
    )
    if value
]
budget = team.bank + sum(player.selling_price for player in team.players)
context_cols = st.columns(4)
context_cols[0].metric("Chip budget", f"£{budget:.1f}m")
context_cols[1].metric("Available chips", len(available))
context_cols[2].metric("Strategy", base_profile.preset)
context_cols[3].metric("Market influence", f"{blend:.0%}")
st.caption("Currently available: " + (" · ".join(available) if available else "None"))

horizon = st.slider(
    "Evaluation horizon",
    min_value=1,
    max_value=6,
    value=max(1, base_profile.horizon),
    format="%d Gameweeks",
    help="Wildcard gain is measured across the full horizon; other chips affect one Gameweek.",
)
profile = replace(base_profile, horizon=horizon)
team_signature = (
    tuple((p.player_id, p.selling_price) for p in team.players),
    team.bank,
    tuple(available),
)
signature = (team_signature, asdict(profile), blend)

if st.button("Evaluate chip opportunities", type="primary"):
    try:
        with st.spinner("Optimizing chip squads, lineups, and captains…"):
            report = container.chips.run(profile, blend, horizon)
        st.session_state["chip_evaluation"] = {
            "signature": signature,
            "report": report,
        }
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("chip_evaluation")
if isinstance(stored, dict) and stored.get("signature") == signature:
    report = stored["report"]
    evaluation = report.evaluation
    if evaluation.best_chip:
        st.success(
            f"Strongest available opportunity: {evaluation.best_chip} "
            f"(+{evaluation.best_gain:.1f} projected points)"
        )
    else:
        st.warning("No chips are currently marked as available on My Team.")

    comparison = pd.DataFrame(
        [
            {
                "Chip": opportunity.chip,
                "Available": opportunity.available,
                "Best Gameweek": opportunity.recommended_gameweek or "—",
                "Projected gain": opportunity.projected_gain,
                "Players changed": len(opportunity.players_in),
            }
            for opportunity in evaluation.opportunities
        ]
    )
    st.subheader("Opportunity comparison")
    st.dataframe(
        comparison,
        hide_index=True,
        width="stretch",
        column_config={
            "Projected gain": st.column_config.NumberColumn(format="%+.1f pts"),
            "Players changed": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.caption(
        "Wildcard gain covers the full selected horizon. Free Hit, Bench Boost, and Triple "
        "Captain gains are one-Gameweek increments, so compare them with that distinction in mind."
    )

    score_names = {
        score.player_id: f"{score.player} ({score.position}, {score.team})"
        for score in container.strategy.score(profile, blend)
    }
    st.subheader("Chip details")
    for opportunity in evaluation.opportunities:
        status = "available" if opportunity.available else "unavailable"
        with st.expander(
            f"{opportunity.chip} · {status} · {opportunity.projected_gain:+.1f} pts",
            expanded=opportunity.chip == evaluation.best_chip,
        ):
            st.write(opportunity.rationale)
            if opportunity.players_in:
                movement_cols = st.columns(2)
                movement_cols[0].write("**Bring in**")
                movement_cols[0].write(
                    "\n".join(f"- {score_names[player_id]}" for player_id in opportunity.players_in)
                )
                movement_cols[1].write("**Move out**")
                movement_cols[1].write(
                    "\n".join(
                        f"- {score_names[player_id]}" for player_id in opportunity.players_out
                    )
                )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Gameweek": week.gameweek,
                            "Formation": week.formation,
                            "Captain": week.captain,
                            "Projected points": week.projected_points,
                        }
                        for week in opportunity.weeks
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Projected points": st.column_config.NumberColumn(format="%.1f")
                },
            )

    st.info(
        "Only one chip can be active in a Gameweek. Wildcard and Free Hit squads respect your "
        "current selling value plus bank; a Wildcard does not spend saved free transfers."
    )
    st.caption(
        "This evaluates expected points within the selected horizon. It does not value chip "
        "scarcity beyond that horizon, simulate chip outcomes, or combine chips in one Gameweek."
    )
elif stored is not None:
    st.info("Team, chip availability, strategy, or horizon changed. Evaluate again to refresh.")

recent = container.chips.recent()
if recent:
    with st.expander(f"Recent chip evaluations ({len(recent)})"):
        recent_frame = pd.DataFrame(recent)
        recent_frame["Market influence"] = recent_frame["Market influence"] * 100
        st.dataframe(
            recent_frame,
            hide_index=True,
            width="stretch",
            column_config={
                "Market influence": st.column_config.NumberColumn(format="%.0f%%"),
                "Budget": st.column_config.NumberColumn(format="£%.1fm"),
                "Projected gain": st.column_config.NumberColumn(format="%+.1f"),
            },
        )
