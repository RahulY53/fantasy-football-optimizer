"""Advanced baseline-versus-scenario decision workspace."""

from __future__ import annotations

from dataclasses import asdict, replace

import pandas as pd
import streamlit as st
from shared import active_strategy_profile, market_weight, page_setup

from fpl_optimizer.domain.scenarios import ScenarioAssumptions

container = page_setup("What If", "🧭")
st.title("What-if analysis")
st.caption("Change assumptions temporarily and compare exact decisions with the baseline")
st.info(
    "Scenarios use cached forecasts and are never saved back into the model. Running a scenario "
    "does not modify your team, strategy, forecasts, or normal optimizer history."
)

if container.team.get() is None:
    st.warning("Save or import a current 15-player squad on My Team before running scenarios.")
    st.stop()

base_profile = active_strategy_profile()
blend = market_weight()
horizon = st.slider(
    "Scenario horizon",
    min_value=2,
    max_value=6,
    value=max(2, base_profile.horizon),
    format="%d Gameweeks",
)
profile = replace(base_profile, horizon=horizon)
context = container.what_if.context(profile, blend)
if not context.players or not context.gameweeks:
    st.warning(f"Generate forecasts covering {horizon} Gameweeks before building a scenario.")
    st.stop()

player_by_label = {
    f"{item.player} · {item.position} · {item.team}": item.player_id
    for item in context.players
}
label_by_id = {player_id: label for label, player_id in player_by_label.items()}
all_labels = list(player_by_label)
current_labels = [
    label_by_id[item.player_id] for item in context.players if item.is_current
]
target_labels = [
    label_by_id[item.player_id] for item in context.players if not item.is_current
]

forecast_tab, rules_tab, chip_tab = st.tabs(
    ["Forecast assumptions", "Transfer rules", "Chip timing"]
)
with forecast_tab:
    st.subheader("Player availability")
    unavailable_labels = st.multiselect(
        "Players unavailable for the scenario",
        all_labels,
        help="Sets scenario xPts and expected minutes to zero across the horizon.",
    )
    start_options = ["No custom start assumption", *all_labels]
    start_label = st.selectbox("Override one player's start probability", start_options)
    start_probability = None
    if start_label != "No custom start assumption":
        start_probability = float(
            st.slider("Scenario start probability", 0, 100, 60, 5, format="%d%%")
        )

    st.subheader("Team attacking environment")
    team_options = ["No team adjustment", *context.teams]
    attack_team = st.selectbox("Adjust one team's attacking output", team_options)
    attack_change = 0.0
    if attack_team != "No team adjustment":
        attack_change = float(
            st.slider("Attacking xG adjustment", -50, 50, -10, 5, format="%+d%%")
        )
        st.caption(
            "The percentage change applies to the attacking component of each affected player's "
            "cached horizon forecast; defensive components remain unchanged."
        )

with rules_tab:
    st.subheader("Current-squad rules")
    protected_labels = st.multiselect("Never sell", current_labels)
    must_sell_labels = st.multiselect("Must sell", current_labels)
    st.subheader("Transfer-target rules")
    must_buy_labels = st.multiselect(
        "Must buy",
        target_labels,
        max_selections=2,
    )
    excluded_labels = st.multiselect("Exclude from transfers", target_labels)
    st.caption(
        "The exact transfer solver still enforces budget, positions, the three-player club limit, "
        "free transfers, and hit costs. Contradictory rules are rejected."
    )

with chip_tab:
    chip_options = ["Do not force a chip", "Wildcard", "Free Hit", "Bench Boost", "Triple Captain"]
    forced_chip_label = st.selectbox("Force chip timing", chip_options)
    forced_gameweek_id = None
    if forced_chip_label != "Do not force a chip":
        gameweek_by_name = {name: gameweek_id for gameweek_id, name in context.gameweeks}
        selected_gameweek = st.selectbox("Use chip in", list(gameweek_by_name))
        forced_gameweek_id = gameweek_by_name[selected_gameweek]
        if forced_chip_label not in context.available_chips:
            st.warning(
                f"{forced_chip_label} is marked unavailable on My Team. The counterfactual will "
                "still be calculated, but it cannot currently be played."
            )

assumptions = ScenarioAssumptions(
    start_player_id=(
        player_by_label[start_label] if start_label != "No custom start assumption" else None
    ),
    start_probability=start_probability,
    unavailable_player_ids=tuple(player_by_label[label] for label in unavailable_labels),
    attack_team=attack_team if attack_team != "No team adjustment" else None,
    attack_change=attack_change,
    protected_player_ids=tuple(player_by_label[label] for label in protected_labels),
    must_sell_player_ids=tuple(player_by_label[label] for label in must_sell_labels),
    must_buy_player_ids=tuple(player_by_label[label] for label in must_buy_labels),
    excluded_player_ids=tuple(player_by_label[label] for label in excluded_labels),
    forced_chip=forced_chip_label if forced_chip_label != "Do not force a chip" else None,
    forced_gameweek_id=forced_gameweek_id,
)
signature = (asdict(profile), blend, asdict(assumptions))

if st.button("Run what-if scenario", type="primary"):
    try:
        with st.spinner("Re-scoring assumptions and solving baseline and scenario decisions…"):
            report = container.what_if.run(profile, blend, assumptions)
        st.session_state["what_if_report"] = {"signature": signature, "report": report}
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("what_if_report")
if isinstance(stored, dict) and stored.get("signature") == signature:
    report = stored["report"]
    baseline = report.baseline_transfers
    scenario = report.scenario_transfers
    changed = baseline.recommendation != scenario.recommendation
    if changed:
        st.success(
            f"Decision changed: {baseline.recommendation} → {scenario.recommendation}"
        )
    else:
        st.success(f"Decision is robust: {scenario.recommendation}")

    st.subheader("Active assumptions")
    st.write("\n".join(f"- {label}" for label in report.assumptions))

    comparison = st.columns(4)
    comparison[0].metric("Baseline decision", baseline.recommendation)
    comparison[1].metric("Scenario decision", scenario.recommendation)
    comparison[2].metric(
        f"Baseline {horizon}GW squad xPts", f"{baseline.current_squad_xpts:.1f}"
    )
    comparison[3].metric(
        f"Scenario {horizon}GW squad xPts",
        f"{scenario.current_squad_xpts:.1f}",
        delta=f"{scenario.current_squad_xpts - baseline.current_squad_xpts:+.1f}",
    )

    st.subheader("Transfer alternatives")
    transfer_rows = []
    for case, evaluation in (("Baseline", baseline), ("Scenario", scenario)):
        for plan in evaluation.plans:
            transfer_rows.append(
                {
                    "Case": case,
                    "Plan": "Roll" if plan.transfers == 0 else f"{plan.transfers} transfer(s)",
                    "Moves": "; ".join(
                        f"{move.out_player} → {move.in_player}" for move in plan.moves
                    ) or "Keep squad",
                    "Gross gain": plan.gross_gain,
                    "Hit": plan.hit_cost,
                    "Net gain": plan.net_gain,
                    "Ending bank": plan.ending_bank,
                }
            )
    transfer_frame = pd.DataFrame(transfer_rows)
    st.dataframe(
        transfer_frame,
        hide_index=True,
        width="stretch",
        column_config={
            "Gross gain": st.column_config.NumberColumn(format="%+.1f"),
            "Hit": st.column_config.NumberColumn(format="%d"),
            "Net gain": st.column_config.NumberColumn(format="%+.1f"),
            "Ending bank": st.column_config.NumberColumn(format="£%.1fm"),
        },
    )

    if report.impacts:
        st.subheader("Forecast sensitivity")
        impact_frame = pd.DataFrame([asdict(row) for row in report.impacts]).rename(
            columns={
                "player": "Player",
                "team": "Team",
                "baseline_xpts": "Baseline xPts",
                "scenario_xpts": "Scenario xPts",
                "change": "Change",
            }
        )
        st.dataframe(
            impact_frame.drop(columns=["player_id"]),
            hide_index=True,
            width="stretch",
            column_config={
                "Baseline xPts": st.column_config.NumberColumn(format="%.2f"),
                "Scenario xPts": st.column_config.NumberColumn(format="%.2f"),
                "Change": st.column_config.NumberColumn(format="%+.2f"),
            },
        )
        st.download_button(
            "Export scenario comparison",
            impact_frame.to_csv(index=False).encode("utf-8"),
            "fpl_what_if_scenario.csv",
            "text/csv",
        )

    if report.scenario_chip is not None and report.baseline_chip is not None:
        st.subheader("Forced chip comparison")
        chip_cols = st.columns(3)
        chip_cols[0].metric("Chip", report.scenario_chip.chip)
        chip_cols[1].metric("Gameweek", report.scenario_chip.recommended_gameweek or "—")
        chip_cols[2].metric(
            "Scenario gain",
            f"{report.scenario_chip.projected_gain:+.1f}",
            delta=(
                f"{report.scenario_chip.projected_gain - report.baseline_chip.projected_gain:+.1f} "
                "vs unchanged forecasts"
            ),
        )
        st.write(report.scenario_chip.rationale)

    st.caption(
        "Scenario outputs are counterfactual decision support, not new forecasts. "
        "Start-probability changes use an explicit starter/substitute minutes approximation; "
        "team changes affect only the cached attacking component."
    )
elif stored is not None:
    st.info("Scenario controls changed. Run the scenario again to refresh the comparison.")
