# What-if analysis

The What-if workspace compares an untouched baseline decision with a temporary set of assumptions.
It is intended for questions that should not rewrite the stored forecast, strategy, or current team.

## Supported assumptions

- Override one player's probability of starting.
- Mark one or more players unavailable across the selected horizon.
- Increase or decrease one club's attacking environment.
- Protect current players from sale.
- Require a current player to be sold.
- Require or exclude transfer targets.
- Force Wildcard, Free Hit, Bench Boost, or Triple Captain into a selected Gameweek.

The adjusted inputs are rescored through the active strategy and passed to the existing exact
transfer and chip solvers. Budget, positional quotas, the three-player club limit, free transfers,
hit costs, selling prices, and chip squad rules remain active.

## Forecast transformations

A start-probability override uses a transparent approximation: a start is modeled as 90 minutes
and a non-start as a 20-minute substitute appearance. The resulting expected-minutes ratio scales
the player's cached forecast components.

A club attack adjustment changes only the attacking component of each affected player's cached
horizon projection. Appearance, clean-sheet, defensive-contribution, and other non-attacking
components are not multiplied by the club adjustment.

An unavailable player receives zero expected minutes and zero forecast points throughout the
scenario horizon.

These transformations are sensitivity tools, not newly trained forecasts.

## Outputs

The page shows:

- Whether the transfer recommendation changes or remains robust.
- Baseline and scenario current-squad xPts.
- Legal roll, one-transfer, and two-transfer alternatives.
- Player-level forecast movements caused by the assumptions.
- Baseline and adjusted value of a forced chip in the selected Gameweek.
- A local CSV export of forecast sensitivity.

All scenario results stay in the browser session. They are not written to forecast tables,
optimizer history, strategies, or the saved current team.
