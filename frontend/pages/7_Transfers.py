"""Current-team transfer decision workspace."""

from __future__ import annotations

from dataclasses import asdict, replace

import pandas as pd
import streamlit as st
from shared import active_strategy_profile, market_weight, page_setup

container = page_setup("Transfers", "🔁")
st.markdown('<div class="fpl-kicker">Squad moves</div>', unsafe_allow_html=True)
st.title("Transfers")
st.caption("Compare rolling with the best affordable one- and two-transfer options.")

team = container.team.get()
if team is None:
    st.info("Save your 15-player squad on **My Team** before evaluating transfers.")
    st.stop()

base_profile = active_strategy_profile()
blend = market_weight()

context_cols = st.columns(4)
context_cols[0].metric("Bank", f"£{team.bank:.1f}m")
context_cols[1].metric("Free transfers", team.free_transfers)
context_cols[2].metric("Strategy", base_profile.preset)
context_cols[3].metric("Market influence", f"{blend:.0%}")

with st.expander("Fine-tune this recommendation"):
    control_cols = st.columns(2)
    horizon = control_cols[0].slider(
        "Planning horizon",
        min_value=1,
        max_value=6,
        value=base_profile.horizon,
        format="%d Gameweeks",
        help="Compares each full squad's projected points over this many Gameweeks.",
    )
    reluctance = control_cols[1].slider(
        "Transfer reluctance",
        min_value=0,
        max_value=100,
        value=base_profile.transfer_reluctance,
        help="Higher values require a larger projected gain before spending a free transfer.",
    )
profile = replace(base_profile, horizon=horizon, transfer_reluctance=reluctance)

team_signature = (
    tuple(
        (player.player_id, player.purchase_price, player.selling_price)
        for player in team.players
    ),
    team.bank,
    team.free_transfers,
)
signature = (team_signature, asdict(profile), blend)

if st.button("Find my best transfer decision", type="primary", width="stretch"):
    try:
        with st.spinner("Solving the best legal transfer alternatives…"):
            report = container.transfers.run(profile, blend)
        st.session_state["transfer_evaluation"] = {
            "signature": signature,
            "report": report,
        }
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("transfer_evaluation")
if isinstance(stored, dict) and stored.get("signature") == signature:
    report = stored["report"]
    evaluation = report.evaluation
    labels = {0: "ROLL TRANSFER", 1: "MAKE 1 TRANSFER", 2: "MAKE 2 TRANSFERS"}
    with st.container(border=True):
        st.markdown("### Recommended action")
        st.markdown(f"## {labels[evaluation.recommended_transfers]}")
        st.write(evaluation.rationale)

    summary_cols = st.columns(4)
    summary_cols[0].metric(
        f"Current {evaluation.horizon}GW squad xPts",
        f"{evaluation.current_squad_xpts:.1f}",
    )
    summary_cols[1].metric("Roll flexibility value", f"{evaluation.roll_flexibility_value:.1f}")
    summary_cols[2].metric("Saved run", f"#{report.run_id}")
    summary_cols[3].metric("Alternatives solved", len(evaluation.plans))

    alternatives = pd.DataFrame(
        [
            {
                "Plan": "Roll" if plan.transfers == 0 else f"{plan.transfers} transfer(s)",
                "Gross xPts gain": plan.gross_gain,
                "Hit cost": plan.hit_cost,
                "Net gain": plan.net_gain,
                "Ending bank": plan.ending_bank,
                f"Final {evaluation.horizon}GW squad xPts": plan.final_squad_xpts,
            }
            for plan in evaluation.plans
        ]
    )
    st.subheader("Alternative comparison")
    st.dataframe(
        alternatives,
        hide_index=True,
        width="stretch",
        column_config={
            "Gross xPts gain": st.column_config.NumberColumn(format="%+.1f"),
            "Hit cost": st.column_config.NumberColumn(format="-%d pts"),
            "Net gain": st.column_config.NumberColumn(format="%+.1f"),
            "Ending bank": st.column_config.NumberColumn(format="£%.1fm"),
            f"Final {evaluation.horizon}GW squad xPts": st.column_config.NumberColumn(
                format="%.1f"
            ),
        },
    )

    st.subheader("Transfer details")
    for plan in evaluation.plans:
        title = "Roll transfer" if plan.transfers == 0 else f"Make {plan.transfers} transfer(s)"
        with st.expander(title, expanded=plan.transfers == evaluation.recommended_transfers):
            if not plan.moves:
                st.write("Keep the current squad and preserve the free transfer.")
                continue
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Position": move.position,
                            "OUT": move.out_player,
                            "Selling price": move.selling_price,
                            "IN": move.in_player,
                            "Buy price": move.buy_price,
                            "Bank change": move.budget_change,
                            f"{evaluation.horizon}GW xPts gain": move.horizon_xpts_gain,
                        }
                        for move in plan.moves
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Selling price": st.column_config.NumberColumn(format="£%.1fm"),
                    "Buy price": st.column_config.NumberColumn(format="£%.1fm"),
                    "Bank change": st.column_config.NumberColumn(format="%+.1fm"),
                    f"{evaluation.horizon}GW xPts gain": st.column_config.NumberColumn(
                        format="%+.1f"
                    ),
                },
            )
            st.caption(
                f"Gross gain {plan.gross_gain:+.1f} · hit {plan.hit_cost} · "
                f"net {plan.net_gain:+.1f} · ending bank £{plan.ending_bank:.1f}m"
            )

    st.info(
        "The recommendation spends a transfer only when its net projected gain exceeds the "
        "roll flexibility value. That threshold rises from 0.5 to 3.0 points with transfer "
        "reluctance. xPts remain unchanged by this preference."
    )
    st.caption(
        "This is a static full-squad comparison. It does not yet optimize future weekly lineups, "
        "captaincy, price changes, chips, or a multi-week sequence of transfers."
    )
elif stored is not None:
    st.info("Team or decision settings changed. Evaluate again to refresh the recommendation.")

recent = container.transfers.recent()
if recent:
    with st.expander(f"Recent transfer evaluations ({len(recent)})"):
        st.dataframe(
            pd.DataFrame(recent),
            hide_index=True,
            width="stretch",
            column_config={
                "Bank": st.column_config.NumberColumn(format="£%.1fm"),
                "Reluctance": st.column_config.NumberColumn(format="%d/100"),
            },
        )
