# Weekly Decision Dashboard

Release 7 adds a primary weekly workflow that composes the application's established forecasting,
optimization, planning, simulation, and chip engines into one decision card.

## Update modes

**Update & optimize my team** runs the full public workflow:

1. Refresh official FPL data.
2. Refresh the saved public FPL Team ID squad.
3. Generate six-Gameweek statistical forecasts.
4. Refresh live odds when configured, falling back transparently when unavailable.
5. Optimize the legal starting XI, captain, vice-captain, and bench.
6. Compare rolling with the best legal one- and two-transfer plans.
7. Build a joint multi-Gameweek transfer and lineup path.
8. Run 2,500 reproducible current-squad simulations.
9. Evaluate Wildcard, Free Hit, Bench Boost, and Triple Captain opportunities.

**Use cached data** runs steps 5–9 without network calls. It is useful for testing strategy changes
or working offline, but its recommendation is only as current as the cached inputs.

## Decision card

The card reports:

- Recommended action: roll, transfer, hit, or a modeled current-Gameweek chip opportunity
- Rationale and strongest transfer alternative
- Starting XI, captain, vice-captain, formation, and ordered bench
- Expected score, 3GW outlook, and 5GW outlook
- Transfer details, hit cost, and ending bank
- Multi-Gameweek plan and current-squad simulation range
- Recommendation confidence and risk

A chip replaces the transfer headline only when the chip engine selects the first modeled
Gameweek and its projected gain is at least three points and no weaker than the recommended
transfer plan. Future chip opportunities remain visible in the outlook without being presented as
this week's action.

## Confidence methodology

Confidence is a transparent 0–100 decision-quality score, not a calibrated guarantee:

- **45% decision clarity:** separation between the recommended transfer plan, roll-flexibility
  threshold, and strongest alternative.
- **30% lineup reliability:** expected minutes and modeled downside risk across the starting XI.
- **25% simulation certainty:** simulated outcome spread relative to the current-squad mean.
- **Data-warning penalty:** five points per live-update warning, capped at 20 points.

Labels are High at 75+, Medium at 55–74, and Low below 55. Risk separately combines starting-XI
risk with the simulation coefficient of variation.

## Important interpretation

The planner and simulation intentionally describe different scenarios. The planner optimizes future
transfers and weekly decisions; the simulation holds the current squad fixed. Confidence therefore
measures the quality and separation of the current recommendation—it is not yet optimization
frequency across perturbed transfer solutions. A later robustness release can add that stronger
probability-of-recommendation measure without changing this dashboard contract.
