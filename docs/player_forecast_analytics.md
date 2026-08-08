# Player forecast analytics

The **Forecast** tab on the Player Analytics page compares two to five selected players across
the next 1, 3, 5, or 6 Gameweeks. It reads the latest persisted statistical and market forecasts;
changing the horizon or chart view does not rerun forecasting or optimization.

## Fixture comparison

Each Gameweek cell shows the opponent and two separate 1–5 difficulty ratings:

- **A** measures attacking difficulty from the opponent's official FPL defensive strength.
- **D** measures defensive difficulty from the opponent's official FPL attacking strength.

The opponent's home/away strength is used for the actual venue. Double-Gameweek ratings are
averaged and blanks remain explicitly marked. Ratings are min-max scaled against the current
official FPL team-strength universe: 1 is easier and 5 is harder. They are descriptive fixture
context, not an additional hidden adjustment to xPts.

## Forecast charts

- **Weekly xPts** exposes fixture swings that a horizon total can hide.
- **Cumulative xPts** shows when one player overtakes another during the selected horizon.

Both charts use raw blended expected points. Hover details retain statistical xPts, market xPts,
expected minutes, opponent, and forecast confidence. The page also identifies the comparison
universe, horizon, and forecast timestamp.

## CSV exports

The analytics page provides three local CSV downloads:

- the complete currently filtered player dataset;
- the selected raw comparison table;
- the selected long-form per-Gameweek forecast comparison.

No paid export service or remote storage is involved.
