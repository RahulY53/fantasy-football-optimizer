"""Connection, freshness, and manual refresh controls for optional live data."""

from __future__ import annotations

import streamlit as st
from shared import format_timestamp, page_setup

container = page_setup("Data Sources", "🔌")
st.title("Settings · Data Sources")
st.caption("Manage optional live providers without exposing credentials in the browser")

status = container.live_odds.status()
st.subheader("Live betting odds")
columns = st.columns(4)
columns[0].metric("Provider", "Odds-API.io")
columns[1].metric("Configuration", "CONNECTED" if status.configured else "DISCONNECTED")
columns[2].metric(
    "Last sync", format_timestamp(status.last_sync) if status.last_sync else "Never"
)
columns[3].metric("Freshness", "STALE ODDS" if status.stale else "Fresh")

if not status.configured:
    st.info(
        "Add `FPL_OPTIMIZER_ODDS_API_KEY` to your local `.env` file and restart the app. "
        "The key is used only by the backend and is never stored in the database."
    )

actions = st.columns(2)
if actions[0].button("Test connection", disabled=not status.configured, width="stretch"):
    try:
        if container.live_odds.test_connection():
            st.success("Odds-API.io connection is available.")
    except RuntimeError as error:
        st.error(str(error))
if actions[1].button("Refresh odds", disabled=not status.configured, width="stretch"):
    try:
        with st.spinner("Fetching EPL events, matching fixtures, and rebuilding market xPts…"):
            report = container.live_odds.refresh(force=True)
        source = "cached fallback" if report.from_cache else "live provider"
        st.success(
            f"Matched {report.matched}/{report.events} events and saved {report.inserted} new "
            f"observations from the {source}."
        )
        for warning in report.warnings:
            st.warning(warning)
        st.rerun()
    except RuntimeError as error:
        st.error(str(error))

provider = container.live_odds.provider
remaining = getattr(provider, "rate_limit_remaining", None)
requests = getattr(provider, "requests_made", 0)
st.caption(
    f"Requests this app session: {requests} · "
    f"Provider requests remaining: {remaining if remaining is not None else 'not reported'}"
)
st.caption(f"Effective bookmakers: {getattr(provider, 'bookmakers', 'Provider default')}")
st.write(
    "Normal updates respect the configured cache window. A manual refresh bypasses freshness, "
    "but provider failure still uses the latest valid cached odds when available."
)
st.warning(
    "Fixture links below 85% confidence are rejected. Odds are forecast inputs only and never "
    "become strategy preference scores."
)
