# Interactive 2×2 player matrix

The Player Analytics matrix plots two registered metrics in their original units. It operates on
the same cached player dataset and combined filters as Explorer and Compare, so changing an axis,
reference method, preset, label, point size, or point colour does not rerun forecasting or
optimization.

## Populations and axes

Users can plot all filtered players, manually selected comparison players, one position, selected
clubs, the saved current squad, or the top strategy-adjusted optimization candidates. A player is
omitted only when either selected axis is unavailable; the page reports the omitted count.

Every numeric metric comes from the central registry. Axes remain raw—for example pounds millions,
expected points, percentage ownership, or risk score. The only derived matrix metrics are explicit
ratios: five-Gameweek xPts per £m and next-Gameweek xPts scaled to 90 expected minutes. Market edge
is the stored market xPts minus statistical xPts.

## Reference lines and quadrants

Vertical and horizontal reference lines support the current population median, mean, the median
for a chosen position, or custom raw values. Quadrants include plain-language labels and rank their
top five players by current Optimization Score. Points equal to a reference line are assigned to
the upper or right quadrant consistently.

## Presets

Available presets depend on current data coverage:

- Value Map: Price vs 5GW xPts
- Attacking Threat: Goal xPts vs Assist xPts
- Reliability vs Forecast Upside: Risk vs 5GW xPts
- Minutes vs Output: Expected Minutes vs next-GW xPts per 90
- Ownership vs Expectation: Ownership vs 5GW xPts
- Market vs Model: Statistical xPts vs Market xPts, with a raw `y = x` agreement line
- Market Disagreement: Statistical xPts vs Market Edge

The release does not invent ceiling or VORP. Those presets can be added after the corresponding
forecast and replacement-value models are implemented.

## Interaction

Hover shows the player's full name, club, position, price, both axis values, blended xPts, expected
minutes, ownership, risk, and Optimization Score. Point colour can represent position, club, or
risk category. Point size can represent price, ownership, blended xPts, or Optimization Score.
Labels can show selected players, the top N candidates, every player, or no names.
