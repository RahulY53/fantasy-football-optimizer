"""State-aware FPL Optimizer command centre."""

from __future__ import annotations

import streamlit as st
from shared import active_strategy_profile, format_timestamp, page_setup

from fpl_optimizer.database.forecast_repository import ForecastRepository
from fpl_optimizer.database.repositories import FplRepository

container = page_setup("Home", "⚽")

st.markdown('<div class="fpl-kicker">Gameweek command centre</div>', unsafe_allow_html=True)
st.title("Make the next FPL decision")
st.caption("Update your squad, get one recommendation, then inspect the evidence only if needed.")

with container.database.session() as session:
    repository = FplRepository(session)
    counts = repository.counts()
    freshness = repository.freshness()
    forecast_freshness = ForecastRepository(session).latest_prediction_at()

team = container.team.get()
published = container.team_import.get_summary()
profile = active_strategy_profile()

if not counts["players"]:
    with st.container(border=True):
        st.subheader("Start with official FPL data")
        st.write("Open **Data & model settings** in the sidebar and refresh FPL data.")
        st.caption("Successful downloads are cached locally for offline use.")
elif team is None:
    with st.container(border=True):
        st.markdown("### Your next step")
        st.subheader("Connect or create your team")
        st.write("Import your public FPL Team ID, or manually save a legal 15-player squad.")
        st.page_link("pages/0_My_Team.py", label="Set up My Team", icon="⚽")
else:
    identity = published.team_name if published else team.name
    st.markdown(f"### {identity}")
    if published:
        st.caption(f"Managed by {published.manager_name}")
    status_cols = st.columns(3)
    status_cols[0].metric("Bank", f"£{team.bank:.1f}m")
    status_cols[1].metric("Free transfers", team.free_transfers)
    status_cols[2].metric("Strategy", profile.preset)

    with st.container(border=True):
        st.markdown("### Ready for this Gameweek")
        st.write(
            "Build one consolidated recommendation for transfers, lineup, captaincy, chips, "
            "and the next few Gameweeks."
        )
        action_cols = st.columns([2, 1, 1])
        with action_cols[0]:
            st.page_link(
                "pages/14_Weekly_Dashboard.py",
                label="Open this week's decision",
                icon="📋",
                use_container_width=True,
            )
        with action_cols[1]:
            st.page_link(
                "pages/7_Transfers.py",
                label="Transfers",
                icon="🔁",
                use_container_width=True,
            )
        with action_cols[2]:
            st.page_link(
                "pages/0_My_Team.py",
                label="My Team",
                icon="⚽",
                use_container_width=True,
            )

st.subheader("The weekly workflow")
workflow_cols = st.columns(3)
with workflow_cols[0].container(border=True):
    st.markdown("#### 1 · Update")
    st.write("Refresh your public squad and the latest available evidence.")
with workflow_cols[1].container(border=True):
    st.markdown("#### 2 · Decide")
    st.write("Get one clear action, optimized XI, and captain recommendation.")
with workflow_cols[2].container(border=True):
    st.markdown("#### 3 · Explore")
    st.write("Open transfers, forecasts, or scenarios only when you need more detail.")

with st.expander("Data readiness"):
    readiness_cols = st.columns(4)
    readiness_cols[0].metric("Players", counts["players"])
    readiness_cols[1].metric("Fixtures", counts["fixtures"])
    readiness_cols[2].metric("Official data", "Ready" if freshness else "Missing")
    readiness_cols[3].metric("Forecasts", "Ready" if forecast_freshness else "Missing")
    if freshness:
        st.caption(f"Official data updated {format_timestamp(freshness)}")
    if forecast_freshness:
        st.caption(f"Forecasts generated {format_timestamp(forecast_freshness)}")

with st.expander("What is included in the model?"):
    st.write(
        "Expected minutes, goals, assists, clean sheets, saves, defensive contributions, bonus, "
        "deductions, fixtures, market signals, transfer costs, squad rules, chips, and uncertainty."
    )
    st.caption(
        "Advanced analysis remains available under Explore and Advanced tools in the sidebar."
    )
