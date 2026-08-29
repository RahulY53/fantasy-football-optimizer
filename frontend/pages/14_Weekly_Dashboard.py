"""Primary weekly FPL decision dashboard."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st
from shared import (
    active_strategy_profile,
    format_timestamp,
    market_weight,
    page_setup,
)

from fpl_optimizer.services.weekly import WeeklyDecisionReport

container = page_setup("This Week", "📋")
st.markdown('<div class="fpl-kicker">Your decision</div>', unsafe_allow_html=True)
st.title("This week")
st.caption("One recommended action, with the lineup and evidence behind it.")

team = container.team.get()
published = container.team_import.get_summary()
if team is None:
    st.info(
        "Import or save a legal 15-player squad on **My Team** before building a weekly decision."
    )
    st.stop()

profile = active_strategy_profile()
blend = market_weight()
team_signature = (
    tuple(
        (player.player_id, player.purchase_price, player.selling_price)
        for player in team.players
    ),
    team.bank,
    team.free_transfers,
)
signature = (team_signature, asdict(profile), blend)

st.markdown(f"### {published.team_name if published else team.name}")
context_columns = st.columns(3)
context_columns[0].metric("Bank", f"£{team.bank:.1f}m")
context_columns[1].metric("Free transfers", team.free_transfers)
context_columns[2].metric("Strategy", profile.preset)
rank = f"{published.overall_rank:,}" if published and published.overall_rank else "not available"
st.caption(f"Overall rank {rank} · market influence {blend:.0%}")

with st.container(border=True):
    st.markdown("### Build your recommendation")
    st.write("Refresh everything for the newest view, or use saved data for a faster result.")
    action_columns = st.columns([2, 1])
    live_disabled = published is None or published.published_gameweek == 0
    if action_columns[0].button(
        "Refresh & build decision",
        type="primary",
        width="stretch",
        disabled=live_disabled,
        help=(
            "Refreshes FPL data, your public squad, forecasts, and available odds before running "
            "the decision engines."
        ),
    ):
        try:
            if published is None:
                raise RuntimeError("Import a public FPL Team ID on My Team first")
            with st.spinner("Updating your team and building this week's recommendation…"):
                report = container.weekly.run_live(
                    published.fpl_team_id,
                    profile,
                    blend,
                )
            st.session_state["weekly_decision"] = {
                "signature": signature,
                "report": report,
            }
            st.rerun()
        except (RuntimeError, ValueError) as error:
            st.error(str(error))

    if action_columns[1].button(
        "Use saved data",
        width="stretch",
        help="Builds the recommendation from the latest local data without network calls.",
    ):
        try:
            with st.spinner("Building your recommendation from saved data…"):
                report = container.weekly.run_cached(profile, blend)
            st.session_state["weekly_decision"] = {
                "signature": signature,
                "report": report,
            }
            st.rerun()
        except (RuntimeError, ValueError) as error:
            st.error(str(error))

    if live_disabled:
        st.caption(
            "Live refresh unlocks once a public Gameweek squad is available. Saved-data analysis "
            "still works with a manually created team."
        )

stored = st.session_state.get("weekly_decision")
if not isinstance(stored, dict):
    st.info("Build a recommendation to see your action, lineup, captain, and alternatives here.")
    st.stop()
if stored.get("signature") != signature:
    st.warning(
        "The team, strategy, or market blend changed. Run the dashboard again before relying on "
        "the previous recommendation."
    )
    st.stop()

report = stored.get("report")
if not isinstance(report, WeeklyDecisionReport):
    st.info("Run the dashboard again to refresh its saved browser-session result.")
    st.stop()
summary = report.summary

for warning in report.warnings:
    st.warning(warning)

with st.container(border=True):
    st.markdown("### THIS WEEK")
    st.markdown(f"## {summary.action}")
    st.write(summary.rationale)
    card_columns = st.columns(5)
    card_columns[0].metric(
        "Confidence",
        f"{summary.confidence_label} · {summary.confidence_score:.0f}%",
    )
    card_columns[1].metric("Projected score", f"{summary.projected_score:.1f}")
    card_columns[2].metric("Risk", f"{summary.risk_label} · {summary.risk_score:.0f}/100")
    card_columns[3].metric("Captain", summary.captain)
    card_columns[4].metric("Formation", summary.formation)
    st.caption(
        f"Alternative: **{summary.alternative}** · {summary.alternative_gain:+.1f} net projected "
        f"points · vice-captain **{summary.vice_captain}**"
    )

overview_tab, lineup_tab, transfers_tab, outlook_tab, confidence_tab = st.tabs(
    ["Decision", "Lineup", "Transfers", "Outlook", "Confidence"],
    key="weekly_dashboard_tabs",
    on_change="rerun",
)

with overview_tab:
    st.subheader("Recommended action")
    recommended_plan = next(
        plan
        for plan in report.transfers.evaluation.plans
        if plan.transfers == report.transfers.evaluation.recommended_transfers
    )
    if summary.action_kind == "Chip":
        st.success(f"{summary.action}: {summary.rationale}")
        st.caption(
            f"Underlying no-chip transfer decision: "
            f"**{report.transfers.evaluation.recommendation}**. Chip and transfer projections "
            "are shown as separate scenarios."
        )
    elif recommended_plan.moves:
        st.dataframe(
            pd.DataFrame(
                {
                    "Position": move.position,
                    "OUT": move.out_player,
                    "Sell": move.selling_price,
                    "IN": move.in_player,
                    "Buy": move.buy_price,
                    f"{report.transfers.evaluation.horizon}GW xPts gain": move.horizon_xpts_gain,
                }
                for move in recommended_plan.moves
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Sell": st.column_config.NumberColumn(format="£%.1fm"),
                "Buy": st.column_config.NumberColumn(format="£%.1fm"),
                f"{report.transfers.evaluation.horizon}GW xPts gain": (
                    st.column_config.NumberColumn(format="%+.1f")
                ),
            },
        )
    else:
        st.success("Keep the current squad and preserve the free transfer.")

    decision_columns = st.columns(4)
    decision_columns[0].metric("Starting XI xPts", f"{report.lineup.result.base_xpts:.1f}")
    decision_columns[1].metric(
        "Captain bonus",
        f"{summary.projected_score - report.lineup.result.base_xpts:.1f}",
    )
    decision_columns[2].metric("3GW squad xPts", f"{summary.next_3_squad_xpts:.1f}")
    decision_columns[3].metric("5GW squad xPts", f"{summary.next_5_squad_xpts:.1f}")
    if report.chips.evaluation.best_chip:
        st.info(
            f"Strongest chip opportunity in the modeled horizon: "
            f"**{report.chips.evaluation.best_chip}** "
            f"(+{report.chips.evaluation.best_gain:.1f} projected points)."
        )

with lineup_tab:
    st.subheader(f"Starting XI · {summary.formation}")
    lineup_rows = [
        {
            "Role": player.role,
            "Player": player.player,
            "Position": player.position,
            "Team": player.team,
            "Opponent": player.opponent,
            "Expected minutes": player.expected_minutes,
            "xPts": player.next_gw_xpts,
            "Risk": player.risk,
        }
        for player in report.lineup.result.starters
    ]
    bench_rows = [
        {
            "Role": f"Bench {player.bench_order}",
            "Player": player.player,
            "Position": player.position,
            "Team": player.team,
            "Opponent": player.opponent,
            "Expected minutes": player.expected_minutes,
            "xPts": player.next_gw_xpts,
            "Risk": player.risk,
        }
        for player in report.lineup.result.bench
    ]
    st.dataframe(
        pd.DataFrame([*lineup_rows, *bench_rows]),
        hide_index=True,
        width="stretch",
        column_config={
            "Expected minutes": st.column_config.NumberColumn(format="%.0f"),
            "xPts": st.column_config.NumberColumn(format="%.1f"),
            "Risk": st.column_config.NumberColumn(format="%.0f/100"),
        },
    )
    st.caption(
        "The goalkeeper remains last in the displayed bench order. Captain and vice-captain must "
        "both be in the legal starting XI."
    )

with transfers_tab:
    evaluation = report.transfers.evaluation
    st.subheader("Roll versus transfer alternatives")
    st.dataframe(
        pd.DataFrame(
            {
                "Action": "Roll" if plan.transfers == 0 else f"{plan.transfers} transfer(s)",
                "Gross gain": plan.gross_gain,
                "Hit": plan.hit_cost,
                "Net gain": plan.net_gain,
                "Ending bank": plan.ending_bank,
                "Recommended": plan.transfers == evaluation.recommended_transfers,
            }
            for plan in evaluation.plans
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Gross gain": st.column_config.NumberColumn(format="%+.1f"),
            "Hit": st.column_config.NumberColumn(format="-%d pts"),
            "Net gain": st.column_config.NumberColumn(format="%+.1f"),
            "Ending bank": st.column_config.NumberColumn(format="£%.1fm"),
        },
    )
    st.write(evaluation.rationale)
    st.caption(
        f"Keeping transfer flexibility is currently valued at "
        f"{evaluation.roll_flexibility_value:.1f} projected points."
    )

with outlook_tab:
    st.subheader(f"{report.planner.plan.horizon}-Gameweek optimized path")
    st.dataframe(
        pd.DataFrame(
            {
                "Gameweek": week.gameweek,
                "Transfers": len(week.transfers),
                "Hit": week.hit_cost,
                "Formation": week.formation,
                "Captain": week.captain,
                "Net xPts": week.net_projected_points,
                "Bank after": week.bank_after,
            }
            for week in report.planner.plan.weeks
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Hit": st.column_config.NumberColumn(format="-%d pts"),
            "Net xPts": st.column_config.NumberColumn(format="%.1f"),
            "Bank after": st.column_config.NumberColumn(format="£%.1fm"),
        },
    )
    simulation = report.simulation.result
    simulation_columns = st.columns(6)
    simulation_columns[0].metric("Simulation mean", f"{simulation.mean:.1f}")
    simulation_columns[1].metric("P10 downside", f"{simulation.p10:.1f}")
    simulation_columns[2].metric("P90 upside", f"{simulation.p90:.1f}")
    simulation_columns[3].metric("50/GW+", f"{simulation.probability_50_per_gw_plus:.0%}")
    simulation_columns[4].metric("60/GW+", f"{simulation.probability_60_per_gw_plus:.0%}")
    simulation_columns[5].metric("Iterations", f"{simulation.iterations:,}")
    st.caption(
        "Simulation ranges describe the current squad, while the planner shows an optimized "
        "future transfer path. They are deliberately presented as separate scenarios."
    )

with confidence_tab:
    st.subheader("Why this confidence score?")
    st.dataframe(
        pd.DataFrame(
            {
                "Factor": factor.label,
                "Score": factor.score,
                "Explanation": factor.explanation,
            }
            for factor in summary.confidence_factors
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Score": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.0f%%",
            )
        },
    )
    if report.warnings:
        st.warning(
            f"Confidence includes a {min(20, len(report.warnings) * 5)}-point data-warning "
            "penalty."
        )
    st.info(
        "Confidence is a transparent decision-quality score, not a guarantee. It combines "
        "transfer separation, starting-XI minutes/risk, and simulated outcome spread."
    )

st.caption(
    f"Decision built {format_timestamp(report.created_at)} · lineup run #{report.lineup.run_id} · "
    f"transfer run #{report.transfers.run_id} · planner run #{report.planner.run_id} · "
    f"simulation run #{report.simulation.run_id} · chip run #{report.chips.run_id}."
)
