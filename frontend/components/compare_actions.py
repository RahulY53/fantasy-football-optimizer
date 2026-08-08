"""Session-state handoff helpers for the Player Analytics comparison workspace."""

from __future__ import annotations

import streamlit as st

from fpl_optimizer.analytics.selection import PlayerSelection, normalize_player_selection

PENDING_IDS_KEY = "analytics_pending_compare_ids"
PENDING_SOURCE_KEY = "analytics_pending_compare_source"
COMPARE_IDS_KEY = "analytics_compare_ids"
ANALYTICS_TABS_KEY = "analytics_tabs"


def queue_compare_players(player_ids: list[int] | tuple[int, ...], source: str) -> PlayerSelection:
    """Queue a replacement comparison selection for the analytics page."""

    selection = normalize_player_selection(player_ids)
    st.session_state[PENDING_IDS_KEY] = list(selection.player_ids)
    st.session_state[PENDING_SOURCE_KEY] = source
    return selection


def consume_compare_handoff(valid_ids: set[int]) -> tuple[PlayerSelection | None, str | None]:
    """Apply a queued selection before the comparison widget is instantiated."""

    pending = st.session_state.pop(PENDING_IDS_KEY, None)
    source = st.session_state.pop(PENDING_SOURCE_KEY, None)
    if not isinstance(pending, list):
        return None, None
    selection = normalize_player_selection(pending, valid_ids=valid_ids)
    st.session_state[COMPARE_IDS_KEY] = list(selection.player_ids)
    st.session_state[ANALYTICS_TABS_KEY] = "Compare"
    return selection, str(source) if source else None


def open_compare_page(player_ids: list[int] | tuple[int, ...], source: str) -> None:
    """Queue selected players and navigate directly to the Compare tab."""

    queue_compare_players(player_ids, source)
    st.switch_page("pages/13_Player_Analytics.py")
