# Player Watchlist

Release 5 adds a persistent, local Player Watchlist to Player Analytics. Membership and notes are
stored in SQLite using canonical player IDs; names are display metadata and are never database
keys.

## Tracked information

The Watchlist reuses the latest cached analytics read model to show:

- full name, team, and position;
- price and ownership;
- expected minutes and next opponent;
- statistical/market/blended expected points where available;
- 3GW and 5GW expected points;
- risk and optimization score;
- availability status, injury news, and a user-authored note.

Viewing or filtering the Watchlist does not rerun forecasts, market ingestion, or optimization.
Changing the active strategy or market influence naturally updates the corresponding current
metrics on the next cached analytics refresh.

## Workflows

- Select Player Explorer rows and choose **Add to Watchlist**.
- Add players by searchable full name from the **Watchlist** tab.
- Use **Watchlist only** alongside team, position, price, ownership, minutes, xPts, risk, and
  optimization-score filters.
- Select watched players and open the first five directly in Player Compare.
- Remove players or maintain an individual monitoring note from the Watchlist tab.

## Scope

This release stores membership and notes and always presents current metrics. Historical metric
snapshots and automatic "what changed" alerts belong to the separate change-detection roadmap so
that future deltas have explicit snapshot timing and do not rely on page views.
