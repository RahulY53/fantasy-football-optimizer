# Player Compare workflow

Release 4 connects existing player decision surfaces to the **Compare** tab on Player Analytics.
Selections use canonical player IDs and are limited to five players, matching the comparison table,
radar chart, fixture comparison, and forecast chart limits.

## Selection sources

- **Player Explorer:** select table rows and choose **Compare selected rows**.
- **2×2 Matrix:** click points or use Plotly box/lasso selection, then choose
  **Compare selected matrix points**.
- **My Team:** open **Compare players from My Team**, choose up to five squad members, and open
  Player Compare.
- **Optimizer:** select rows from the latest optimized squad and open them in Player Compare.

Each handoff replaces the previous comparison selection, navigates to Player Analytics, and opens
the Compare tab. Duplicate IDs are removed in input order. If a source supplies more than five
players, only the first five are accepted and the remainder are reported.

## Performance and scope

Selection changes only browser session state. They do not rerun forecasting, market ingestion, or
optimization. The existing cached analytics and per-Gameweek forecast read models serve the
comparison views.

A persistent watchlist is a separate roadmap capability. When added, it can use this same handoff
without introducing another comparison implementation.
