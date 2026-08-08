"""Odds import and market-derived fixture forecast dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import streamlit as st
from shared import page_setup

from fpl_optimizer.database.odds_repository import OddsRepository
from fpl_optimizer.odds.providers.csv_provider import CsvOddsProvider
from fpl_optimizer.odds.providers.manual_provider import ManualOddsProvider

container = page_setup("Markets", "📊")
st.title("Markets")
st.caption("Core and advanced market probabilities, expected goals, and player scoring signals")

live_status = container.live_odds.status()
if live_status.last_sync is not None:
    age_label = "STALE ODDS" if live_status.stale else "Live odds available"
    st.caption(f"{age_label} · last provider sync {live_status.last_sync:%d %b %Y, %H:%M}")
elif not live_status.configured:
    st.info("Live odds are not configured. Manual and CSV markets remain available.")

with container.database.session() as session:
    repository = OddsRepository(session)
    fixture_choices = repository.fixture_choices()
    stored_quotes = repository.quote_count()
    dashboard = repository.market_dashboard()

st.metric("Stored odds observations", stored_quotes)

manual_tab, csv_tab = st.tabs(["Manual entry", "CSV import"])

with manual_tab:
    if not fixture_choices:
        st.info("Refresh official FPL data before entering odds.")
    else:
        labels = dict(fixture_choices)
        with st.form("manual_odds"):
            fixture_id = st.selectbox(
                "Fixture",
                options=list(labels),
                format_func=lambda selected: labels[selected],
            )
            bookmaker = st.text_input("Bookmaker", value="Manual consensus")
            st.write("Match result · decimal odds")
            result_cols = st.columns(3)
            home = result_cols[0].number_input("Home", min_value=1.01, value=2.00, step=0.05)
            draw = result_cols[1].number_input("Draw", min_value=1.01, value=3.50, step=0.05)
            away = result_cols[2].number_input("Away", min_value=1.01, value=4.00, step=0.05)
            st.write("Total goals 2.5 · decimal odds")
            total_cols = st.columns(2)
            over = total_cols[0].number_input("Over 2.5", min_value=1.01, value=1.90, step=0.05)
            under = total_cols[1].number_input("Under 2.5", min_value=1.01, value=1.95, step=0.05)
            advanced = st.checkbox("Add BTTS and team-total markets")
            btts_yes = btts_no = None
            home_over_1_5 = home_under_1_5 = None
            away_over_1_5 = away_under_1_5 = None
            if advanced:
                st.write("Both teams to score · decimal odds")
                btts_cols = st.columns(2)
                btts_yes = btts_cols[0].number_input(
                    "BTTS Yes", min_value=1.01, value=1.80, step=0.05
                )
                btts_no = btts_cols[1].number_input(
                    "BTTS No", min_value=1.01, value=2.00, step=0.05
                )
                st.write("Team totals 1.5 · decimal odds")
                home_cols = st.columns(2)
                home_over_1_5 = home_cols[0].number_input(
                    "Home over 1.5", min_value=1.01, value=1.75, step=0.05
                )
                home_under_1_5 = home_cols[1].number_input(
                    "Home under 1.5", min_value=1.01, value=2.10, step=0.05
                )
                away_cols = st.columns(2)
                away_over_1_5 = away_cols[0].number_input(
                    "Away over 1.5", min_value=1.01, value=2.50, step=0.05
                )
                away_under_1_5 = away_cols[1].number_input(
                    "Away under 1.5", min_value=1.01, value=1.55, step=0.05
                )
            submitted = st.form_submit_button("Save odds snapshot", type="primary")
        if submitted:
            try:
                provider = ManualOddsProvider(
                    fixture_id,
                    bookmaker,
                    datetime.now(UTC),
                    home,
                    draw,
                    away,
                    over,
                    under,
                    btts_yes,
                    btts_no,
                    home_over_1_5,
                    home_under_1_5,
                    away_over_1_5,
                    away_under_1_5,
                )
                report = container.odds_import.import_provider(provider)
                st.success(
                    f"Saved {report.inserted} new observations ({report.total_stored} total)."
                )
            except ValueError as error:
                st.error(str(error))

with csv_tab:
    st.write(
        "Upload long-form decimal odds. Required columns: `fixture_id`, `bookmaker`, "
        "`market`, `selection`, `decimal_odds`, `observed_at`. Add `player_id` for anytime "
        "goalscorer rows; this is the official FPL player ID."
    )
    template = (
        "fixture_id,bookmaker,market,selection,decimal_odds,observed_at,snapshot_kind,player_id\n"
        "1,Example Book,1x2,home,2.00,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,1x2,draw,3.50,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,1x2,away,4.00,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,over_under_2_5,over,1.90,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,over_under_2_5,under,1.95,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,btts,yes,1.80,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,btts,no,2.00,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,home_total_1_5,over,1.75,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,home_total_1_5,under,2.10,2026-08-08T12:00:00Z,current,\n"
        "1,Example Book,anytime_goalscorer,score,2.40,2026-08-08T12:00:00Z,current,101\n"
    )
    st.download_button("Download CSV template", template, "odds_template.csv", "text/csv")
    upload = st.file_uploader("Odds CSV", type=["csv"])
    if upload and st.button("Import CSV odds"):
        try:
            provider = CsvOddsProvider(upload.getvalue(), source_ref=upload.name)
            report = container.odds_import.import_provider(provider)
            st.success(
                f"Imported {report.inserted} new observations ({report.total_stored} total)."
            )
        except ValueError as error:
            st.error(str(error))

st.divider()
run_cols = st.columns([1, 1, 2])
method = run_cols[0].selectbox("De-vig method", ["multiplicative", "power", "shin"])
if run_cols[1].button("Generate market forecasts", type="primary"):
    try:
        with st.spinner("Removing margin and fitting expected goals…"):
            report = container.markets.run(method)
        st.success(
            f"Forecasted {report.fixtures} fixtures and {report.player_forecasts} player rows."
        )
        for warning in report.warnings:
            st.warning(warning)
        st.rerun()
    except (RuntimeError, ValueError) as error:
        st.error(str(error))

st.subheader("Market fixture forecasts")
if dashboard:
    frame = pd.DataFrame(dashboard)
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config={
            column: st.column_config.NumberColumn(column, format="%.1f%%")
            for column in (
                "Home win %",
                "Draw %",
                "Away win %",
                "Over 2.5 %",
                "BTTS %",
                "Home over 1.5 %",
                "Away over 1.5 %",
                "Home CS %",
                "Away CS %",
            )
        }
        | {
            "Home xG": st.column_config.NumberColumn(format="%.2f"),
            "Away xG": st.column_config.NumberColumn(format="%.2f"),
            "Dispersion": st.column_config.NumberColumn(format="%.3f"),
            "Fit residual": st.column_config.NumberColumn(format="%.3f"),
        },
    )
else:
    st.info("Import complete markets, then generate market forecasts.")
