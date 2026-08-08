# Chip planner model card

## Purpose

Phase 11 compares the strongest modeled use of Wildcard, Free Hit, Bench Boost, and Triple Captain
inside a one-to-six-Gameweek horizon. It respects the availability flags saved on My Team and saves
every evaluation with its forecast timestamp, strategy, blend, budget, and complete result.

The implementation follows the current official constraints that only one chip can be active in a
Gameweek, Wildcard and Free Hit remain budget constrained, and saved free transfers are preserved
when a Wildcard is played. Rules can change between seasons, so availability remains explicitly
user-managed. See the [official FPL Help](https://fantasy.premierleague.com/help/).

## Baseline

For each future Gameweek, the current 15-player squad is assigned its highest-xPts legal formation,
starting XI, and captain. The baseline horizon score is the sum of those weekly XI and captain
projections without a chip.

## Wildcard

Wildcard is modeled as an immediate permanent rebuild. One binary mixed-integer program selects a
single legal 15-player squad and separately optimizes its XI and captain in every Gameweek of the
horizon. The reported gain is:

```text
optimized rebuilt-squad points over the horizon - current-squad points over the horizon
```

The budget equals current bank plus the saved selling value of all current players. Retained current
players use their saved selling value in the constraint; incoming players use their current buy
price. Strategy utility is only a tiny deterministic tie-breaker after projected points.

## Free Hit

Free Hit solves a separate exact legal squad, XI, and captain for every Gameweek. It recommends the
week with the largest improvement over the current team's projected score. The squad is explicitly
temporary and the UI states that the original squad is restored afterward.

## Bench Boost

For every Gameweek, Bench Boost gain is the projected xPts of the four players outside the normal
optimal XI. Captaincy is unchanged. The recommended Gameweek has the highest total bench xPts.

## Triple Captain

The normal captain already scores twice. Triple Captain adds one further copy of the selected
captain's xPts, so its incremental gain is that captain's projected score. The best Gameweek and
captain are returned.

## Comparison

The strongest currently available projected gain is highlighted. Wildcard gain spans the entire
selected horizon, whereas Free Hit, Bench Boost, and Triple Captain are one-Gameweek increments.
This makes the headline a useful orientation, not a claim that the four numbers have identical
option value. Only one chip may be used in a Gameweek; chips are never combined by the optimizer.

## Limitations

- The model optimizes expected points, not the Phase 10 outcome distribution.
- It does not reserve a chip for opportunities beyond the selected horizon or model expiry dates.
- Availability is a boolean for the currently usable chip set. The app does not infer half-season
  chip replenishment from an FPL account.
- Wildcard is evaluated as an immediate action, not at every possible future Gameweek.
- Prices and forecasts are static, and future injuries or schedule changes are not simulated.
- Bench Boost ignores autosub interactions because all 15 players score when the chip is active.
- Triple Captain does not model vice-captain inheritance when the captain fails to play.
