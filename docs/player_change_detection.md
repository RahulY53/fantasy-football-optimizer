# Player Change Detection

Release 6 adds **What changed since the last update?** to Player Analytics. It compares the latest
two immutable observations already stored by the application; opening the view never refreshes FPL
data, odds, forecasts, or optimization.

## Changes tracked

- Next-Gameweek, 3GW, and 5GW blended expected points
- Expected minutes
- Player-level market xPts and goalscorer probability
- Price and ownership
- Availability status, chance of playing, and news

Small numeric movements are suppressed so the report focuses on actionable changes. Availability
and news changes are always retained. A significance score is used only for ordering; the UI and CSV
show the underlying raw values and deltas.

## Source windows

Official FPL, statistical forecasts, and market forecasts update independently. The Changes tab
therefore displays a separate previous-to-current timestamp window for each source. A source needs
two distinct observations before it can contribute deltas. The first refresh after this release
starts availability/news history; the following refresh enables availability comparisons.

Blended xPts uses the current **Market influence** setting. To avoid false movements, market data is
included in a before/after blend only when both market observations exist; otherwise both sides use
the statistical model.

## Workflow

1. Refresh official FPL data and generate forecasts as usual.
2. After inputs change, refresh or forecast again.
3. Open **Player Analytics → Changes**.
4. Filter to the Watchlist or selected change types.
5. Select up to five changed players and open them directly in Compare.
6. Download the current report as CSV when needed.

The historical availability table is added by Alembic migration `0017`. Price, ownership, and
forecast changes reuse the application's existing append-only histories.
