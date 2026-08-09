"""FPL Optimizer landing page and capability overview."""

from __future__ import annotations

import streamlit as st
from shared import page_setup

from fpl_optimizer.database.repositories import FplRepository

container = page_setup("Home", "⚽")

st.title("Fantasy Premier League Optimizer")
st.caption("A local-first forecasting and decision engine")

st.success(
    "What-if analysis available: change temporary player, team, transfer, and chip assumptions "
    "and compare the exact decision with the unchanged baseline."
)

with container.database.session() as session:
    repository = FplRepository(session)
    counts = repository.counts()
    freshness = repository.freshness()

if not counts["players"]:
    st.subheader("Start with official FPL data")
    st.write(
        "Refresh from the sidebar to build your local player, team, Gameweek, and fixture "
        "database. The app caches successful downloads for offline use."
    )
else:
    cols = st.columns(4)
    cols[0].metric("Players", counts["players"])
    cols[1].metric("Teams", counts["teams"])
    cols[2].metric("Gameweeks", counts["gameweeks"])
    cols[3].metric("Fixtures", counts["fixtures"])

    st.success("Your local FPL data foundation is ready.")
    st.write(
        "Generate forecasts from the sidebar, choose preferences on **Strategy**, build an initial "
        "squad in **Optimizer**, manage its lineup on **My Team**, then compare transfer plans "
        "on **Transfers**, build a future path on **Planner**, or open **Weekly Dashboard** for "
        "one consolidated recommendation. Advanced users can inspect the pipeline in "
        "**Model Lab** or test assumptions in **What If**."
    )

st.divider()
st.subheader("Data foundation")
st.markdown(
    """
- Resilient official FPL data refresh with atomic local caching
- Timestamped SQLite snapshots and repeatable upserts
- Searchable player browser with availability and performance data
- Fixture browser with Gameweek, difficulty, scheduling, blanks, and results
- Graceful cached fallback when the live service is unavailable
"""
)

st.subheader("Forecasting")
st.markdown(
    """
- Probability-weighted expected minutes with availability and confidence
- 2026/27 goal, assist, clean-sheet, save, defensive-contribution, bonus, and deduction scoring
- Statistical xPts across the next six Gameweeks, including blanks and doubles
- Versioned forecasts with source cutoff timestamps and plain-language limitations
"""
)

st.subheader("Decisions and analytics")
st.markdown(
    """
- Optional odds consensus, implied goals, market xPts, and statistical/market blending
- Simple and Advanced strategy profiles with presets and explainable player utility scores
- Legal 15-player initial-squad optimization with budget, club, lock, and exclusion constraints
- Persistent current squad with prices, bank, transfers, and chip availability
- Exact next-Gameweek formation, starting XI, captain, vice-captain, and bench optimization
- Exact roll, one-transfer, and two-transfer comparisons with bank, free-transfer, and hit costs
- Joint multi-Gameweek transfer, formation, lineup, captain, bank, and free-transfer planning
- BTTS, team totals, goalscorer odds, richer FPL signals, and improved expected minutes
- Reproducible current-team Monte Carlo distributions with correlated club-level outcomes
- Wildcard, Free Hit, Bench Boost, and Triple Captain opportunity evaluation
- Leakage-safe historical outcome imports, chronological backtesting, and blend calibration
- Read-only model, blend, minutes, market, calibration, and feature-influence diagnostics
- Session-only player, team, transfer-rule, and forced-chip what-if comparisons
"""
)
