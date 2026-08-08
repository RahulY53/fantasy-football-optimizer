"""Current squad editor and optimized lineup dashboard."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st
from shared import (
    active_strategy_profile,
    format_timestamp,
    load_forecast_summaries,
    market_weight,
    page_setup,
)

from fpl_optimizer.domain.team import CurrentTeamInput, CurrentTeamPlayerInput

container = page_setup("My Team", "⚽")
st.title("My Team")
st.caption("Manage your current 15-player squad and optimize the next-Gameweek lineup")

existing = container.team.get()
choices = container.team.player_choices()
choice_by_id = {int(row["Player ID"]): row for row in choices}
latest_optimized = container.team.latest_optimized_input()
published = container.team_import.get_summary()

st.subheader("Import FPL Team")
import_cols = st.columns([2, 1, 1, 1])
team_id = import_cols[0].number_input(
    "FPL Team ID",
    min_value=1,
    step=1,
    value=published.fpl_team_id if published else 1,
    help="Imports the latest squad published through the public FPL Gameweek endpoint.",
)
if import_cols[1].button("Import team", type="primary", width="stretch"):
    try:
        with st.spinner("Loading the latest published Gameweek squad…"):
            imported_summary = container.team_import.import_team(int(team_id))
        st.session_state.pop("lineup_result", None)
        if imported_summary.published_gameweek:
            st.success("Published squad imported and saved.")
        else:
            st.success(
                "Team ID verified and saved. The squad will become public after the first deadline."
            )
        st.rerun()
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
if import_cols[2].button("Refresh team", disabled=published is None, width="stretch"):
    try:
        container.team_import.import_team(int(team_id), force=True)
        st.session_state.pop("lineup_result", None)
        st.rerun()
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
if import_cols[3].button(
    "Update my team",
    width="stretch",
    disabled=published is not None and published.published_gameweek == 0,
):
    try:
        with st.spinner("Updating FPL data, squad, odds, forecasts, and recommendations…"):
            update = container.update_team.run(
                int(team_id), active_strategy_profile(), market_weight()
            )
        st.session_state["lineup_result"] = {"signature": None, "report": update.lineup}
        st.session_state["team_update_report"] = update
        st.success("Team and recommendations updated.")
        st.rerun()
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

published = container.team_import.get_summary()
if published is not None:
    status_cols = st.columns(6)
    status_cols[0].metric("Manager", published.manager_name)
    status_cols[1].metric("Team", published.team_name)
    status_cols[2].metric(
        "Overall rank", f"{published.overall_rank:,}" if published.overall_rank else "—"
    )
    status_cols[3].metric("Total points", f"{published.total_points:,}")
    status_cols[4].metric(
        "Squad value", f"£{published.squad_value:.1f}m" if published.squad_value else "—"
    )
    status_cols[5].metric("Bank", f"£{published.bank:.1f}m")
    if published.published_gameweek:
        st.warning(
            f"Team status: **{published.data_status}** for GW{published.published_gameweek}. "
            "The public endpoint may not include transfers made since that deadline; free "
            "transfers and current chip state are unknown."
        )
    else:
        st.info(
            "Team status: **Awaiting first published squad**. Your Team ID is valid and saved, "
            "but FPL does not expose the selected players publicly before the first deadline. "
            "Use Refresh team after Gameweek 1 begins."
        )
    st.caption(
        f"Last refreshed {format_timestamp(published.refreshed_at)} · "
        f"{published.transfer_count} historical transfers loaded"
    )
    role_rows = []
    for order, player_id in enumerate(
        (*published.starting_ids, *published.bench_ids), start=1
    ):
        player = choice_by_id.get(player_id, {})
        if player_id == published.captain_id:
            role = "Starting XI · Captain"
        elif player_id == published.vice_captain_id:
            role = "Starting XI · Vice captain"
        elif player_id in published.starting_ids:
            role = "Starting XI"
        else:
            role = f"Bench {order - len(published.starting_ids)}"
        role_rows.append(
            {
                "Role": role,
                "Player": player.get("Player", f"Player #{player_id}"),
                "Position": player.get("Position", "—"),
                "Team": player.get("Team", "—"),
            }
        )
    if role_rows:
        with st.expander("Published squad, captain, and bench", expanded=True):
            st.dataframe(pd.DataFrame(role_rows), hide_index=True, width="stretch")
    if published.recent_transfers:
        with st.expander("Previous transfers"):
            st.dataframe(
                pd.DataFrame(published.recent_transfers),
                hide_index=True,
                width="stretch",
                column_config={
                    "Sale price": st.column_config.NumberColumn(format="£%.1fm"),
                    "Buy price": st.column_config.NumberColumn(format="£%.1fm"),
                },
            )
    if published.recent_history:
        with st.expander("Recent Gameweek history"):
            history_frame = pd.DataFrame(published.recent_history)
            preferred = [
                column
                for column in (
                    "event",
                    "points",
                    "total_points",
                    "overall_rank",
                    "rank",
                    "value",
                    "bank",
                    "event_transfers",
                    "event_transfers_cost",
                )
                if column in history_frame
            ]
            st.dataframe(history_frame[preferred], hide_index=True, width="stretch")

if st.session_state.pop("team_saved", False):
    st.success("Current squad saved.")

with st.expander("Edit current squad", expanded=existing is None):
    if latest_optimized is not None and st.button("Use latest optimized squad"):
        st.session_state["current_squad_selection"] = [
            player.player_id for player in latest_optimized.players
        ]
        st.session_state["team_bank"] = latest_optimized.bank
        st.session_state["team_free_transfers"] = latest_optimized.free_transfers
        st.rerun()

    existing_ids = [player.player_id for player in existing.players] if existing else []
    labels = {
        player_id: (
            f"{row['Player']} · {row['Position']} · {row['Team']} · £{float(row['Price']):.1f}m"
        )
        for player_id, row in choice_by_id.items()
    }
    selected_ids = st.multiselect(
        "Current squad",
        options=list(labels),
        default=existing_ids,
        format_func=lambda player_id: labels[player_id],
        max_selections=15,
        key="current_squad_selection",
        help="Select exactly 15 players with legal FPL position and club quotas.",
    )
    st.caption(f"{len(selected_ids)}/15 players selected")

    existing_prices = {
        player.player_id: (player.purchase_price, player.selling_price)
        for player in existing.players
    } if existing else {}
    price_rows = [
        {
            "Player ID": player_id,
            "Player": choice_by_id[player_id]["Player"],
            "Position": choice_by_id[player_id]["Position"],
            "Team": choice_by_id[player_id]["Team"],
            "Current price": float(choice_by_id[player_id]["Price"]),
            "Purchase price": existing_prices.get(
                player_id, (float(choice_by_id[player_id]["Price"]), 0.0)
            )[0],
            "Selling price": existing_prices.get(
                player_id, (0.0, float(choice_by_id[player_id]["Price"]))
            )[1],
        }
        for player_id in selected_ids
    ]
    editor_key = "team_prices_" + "_".join(map(str, sorted(selected_ids)))
    edited_prices = st.data_editor(
        pd.DataFrame(price_rows),
        hide_index=True,
        width="stretch",
        disabled=["Player ID", "Player", "Position", "Team", "Current price"],
        key=editor_key,
        column_config={
            "Current price": st.column_config.NumberColumn(format="£%.1fm"),
            "Purchase price": st.column_config.NumberColumn(
                min_value=0.1, max_value=20.0, step=0.1, format="£%.1fm"
            ),
            "Selling price": st.column_config.NumberColumn(
                min_value=0.1, max_value=20.0, step=0.1, format="£%.1fm"
            ),
        },
    )

    meta_cols = st.columns(3)
    bank = meta_cols[0].number_input(
        "Money in bank",
        min_value=0.0,
        max_value=20.0,
        value=existing.bank if existing else 0.0,
        step=0.1,
        key="team_bank",
    )
    free_transfers = meta_cols[1].number_input(
        "Free transfers",
        min_value=0,
        max_value=5,
        value=existing.free_transfers if existing else 1,
        step=1,
        key="team_free_transfers",
    )
    meta_cols[2].caption("These values feed the roll, one-, and two-transfer comparison.")

    st.write("Chips available")
    chip_cols = st.columns(4)
    wildcard = chip_cols[0].checkbox(
        "Wildcard", value=existing.wildcard_available if existing else True
    )
    free_hit = chip_cols[1].checkbox(
        "Free Hit", value=existing.free_hit_available if existing else True
    )
    bench_boost = chip_cols[2].checkbox(
        "Bench Boost", value=existing.bench_boost_available if existing else True
    )
    triple_captain = chip_cols[3].checkbox(
        "Triple Captain", value=existing.triple_captain_available if existing else True
    )

    if st.button("Save current squad", type="primary"):
        try:
            player_inputs = tuple(
                CurrentTeamPlayerInput(
                    player_id=int(row["Player ID"]),
                    purchase_price=float(row["Purchase price"]),
                    selling_price=float(row["Selling price"]),
                )
                for row in edited_prices.to_dict("records")
            )
            container.team.save(
                CurrentTeamInput(
                    name="My Team",
                    bank=float(bank),
                    free_transfers=int(free_transfers),
                    wildcard_available=wildcard,
                    free_hit_available=free_hit,
                    bench_boost_available=bench_boost,
                    triple_captain_available=triple_captain,
                    players=player_inputs,
                )
            )
            st.session_state["team_saved"] = True
            st.session_state.pop("lineup_result", None)
            st.rerun()
        except ValueError as error:
            st.error(str(error))

team = container.team.get()
if team is None:
    st.info("Select and save a legal 15-player current squad to generate a lineup.")
    st.stop()

profile = active_strategy_profile()
blend = market_weight()
signature = (
    tuple(
        (player.player_id, player.purchase_price, player.selling_price) for player in team.players
    ),
    asdict(profile),
    blend,
)
update_report = st.session_state.get("team_update_report")
if update_report is not None:
    st.session_state["lineup_result"] = {
        "signature": signature,
        "report": update_report.lineup,
    }
    for warning in update_report.warnings:
        st.warning(warning)
    recommendation = update_report.transfers.evaluation.recommendation
    best_plan = next(
        plan
        for plan in update_report.transfers.evaluation.plans
        if plan.transfers == update_report.transfers.evaluation.recommended_transfers
    )
    st.info(
        f"Recommended action: **{recommendation}** · "
        f"{best_plan.net_gain:+.1f} projected points over "
        f"{update_report.transfers.evaluation.horizon} Gameweeks"
    )
    st.session_state.pop("team_update_report", None)

summary_cols = st.columns(5)
summary_cols[0].metric("Current value", f"£{sum(p.current_price for p in team.players):.1f}m")
summary_cols[1].metric("Selling value", f"£{sum(p.selling_price for p in team.players):.1f}m")
summary_cols[2].metric("Bank", f"£{team.bank:.1f}m")
summary_cols[3].metric("Free transfers", team.free_transfers)
summary_cols[4].metric("Active strategy", profile.preset)

if st.button("Optimize lineup", type="primary"):
    try:
        with st.spinner("Selecting the best legal XI and captaincy…"):
            report = container.team.optimize(profile, blend)
        st.session_state["lineup_result"] = {"signature": signature, "report": report}
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

stored = st.session_state.get("lineup_result")
if not isinstance(stored, dict) or stored.get("signature") != signature:
    st.info("Optimize the lineup to see formation, captaincy, and bench order.")
    st.stop()

report = stored["report"]
result = report.result
captain = next(player for player in result.starters if player.player_id == result.captain_id)
vice = next(player for player in result.starters if player.player_id == result.vice_captain_id)

headline = st.columns(6)
headline[0].metric("Formation", result.formation)
headline[1].metric("Projected GW points", f"{result.projected_points:.1f}")
headline[2].metric("Next 3 squad xPts", f"{result.next_3_squad_xpts:.1f}")
headline[3].metric("Next 5 squad xPts", f"{result.next_5_squad_xpts:.1f}")
headline[4].metric("Captain", captain.player)
headline[5].metric("Vice captain", vice.player)

if published is not None:
    forecast_by_id = {
        int(row["Player ID"]): float(row["Blended xPts"])
        for row in load_forecast_summaries(container, blend)
    }
    if all(player_id in forecast_by_id for player_id in published.starting_ids):
        published_projection = sum(
            forecast_by_id[player_id] for player_id in published.starting_ids
        ) + forecast_by_id.get(published.captain_id, 0.0)
        comparison = st.columns(3)
        comparison[0].metric("Published XI projection", f"{published_projection:.1f}")
        comparison[1].metric("Optimized XI projection", f"{result.projected_points:.1f}")
        comparison[2].metric(
            "Potential lineup improvement",
            f"{result.projected_points - published_projection:+.1f}",
        )

st.markdown(
    """
    <style>
    .pitch {background: linear-gradient(#248c46, #19733a); border-radius: 18px; padding: 24px 18px;}
    .player-card {background: white; color: #16251c; border-radius: 10px; padding: 9px 6px;
                  text-align: center; box-shadow: 0 2px 7px rgba(0,0,0,.22); min-height: 90px;}
    .player-card strong {font-size: .92rem;} .player-card small {font-size: .72rem; color: #4b5e52;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="pitch">', unsafe_allow_html=True)
for position in ("GK", "DEF", "MID", "FWD"):
    position_players = [player for player in result.starters if player.position == position]
    columns = st.columns(len(position_players))
    for column, player in zip(columns, position_players, strict=True):
        if player.player_id == result.captain_id:
            badge = " (C)"
        elif player.player_id == result.vice_captain_id:
            badge = " (VC)"
        else:
            badge = ""
        column.markdown(
            f'<div class="player-card"><strong>{player.player}{badge}</strong><br>'
            f'<small>{player.team} · {player.opponent}<br>£{player.current_price:.1f}m · '
            f'{player.expected_minutes:.0f} xMins<br>{player.next_gw_xpts:.1f} xPts</small></div>',
            unsafe_allow_html=True,
        )
st.markdown("</div>", unsafe_allow_html=True)

st.subheader("Bench order")
bench_cols = st.columns(4)
for column, player in zip(bench_cols, result.bench, strict=True):
    label = f"{player.bench_order}." if player.position != "GK" else "GK"
    column.markdown(
        f'<div class="player-card"><strong>{label} {player.player}</strong><br>'
        f'<small>{player.position} · {player.opponent}<br>{player.expected_minutes:.0f} xMins · '
        f'{player.next_gw_xpts:.1f} xPts</small></div>',
        unsafe_allow_html=True,
    )

st.subheader("Captaincy views")
st.dataframe(
    pd.DataFrame(
        [
            {
                "View": option.kind,
                "Player": option.player,
                "Score": option.score,
                "Why": option.rationale,
            }
            for option in result.captain_options
        ]
    ),
    hide_index=True,
    width="stretch",
    column_config={"Score": st.column_config.NumberColumn(format="%.1f")},
)
st.caption(
    f"Projected GW points include {captain.player}'s {captain.next_gw_xpts:.1f} xPts a second "
    "time for captaincy. Future-horizon totals describe the full 15-player squad, not a separately "
    "optimized XI in each future Gameweek."
)

chips = [
    name
    for name, available in (
        ("Wildcard", team.wildcard_available),
        ("Free Hit", team.free_hit_available),
        ("Bench Boost", team.bench_boost_available),
        ("Triple Captain", team.triple_captain_available),
    )
    if available
]
st.info(f"Available chips: {', '.join(chips) if chips else 'None'} · lineup run #{report.run_id}")
