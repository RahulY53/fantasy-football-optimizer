# User Strategy Score — Model Card

Model name: `user-strategy-score`  
Version: `0.4.0`  
Status: Phase 4 explainable decision baseline

## Intended use

The strategy score ranks forecasted FPL players according to a manager's stated preferences. It is
a decision utility score from 0 to 100, not an expected-points forecast and not a claim that a
player will return a particular number of points.

Strategy preferences are applied only after statistical and market forecasts are blended. Changing
a planning horizon, preset, risk appetite, ownership preference, or feature weight cannot alter
the stored forecasts.

## Modes and presets

Simple mode exposes expected points, fixtures, form, value, downside protection, and differential
potential. Advanced mode adds expected minutes, value above replacement, attacking, clean-sheet
and bonus potential, ceiling, consistency, rotation safety, and injury safety.

Built-in profiles are Balanced, Conservative, Aggressive, Value Hunter, Differential, Short-Term
Attack, and Long-Term Planner. A preset is only a starting point: every raw weight remains editable
from 0 (ignore) to 100 (very important), and modified profiles can be saved locally.

## Feature construction

- Expected points: blended xPts summed over the selected one-to-six-Gameweek horizon.
- Fixtures: mean `6 - FPL fixture difficulty` across the horizon, so higher is easier.
- Expected minutes: forecast minutes per scheduled fixture.
- Form and ownership: current official FPL fields at the data cutoff.
- Value: horizon xPts divided by current price in millions.
- Value above replacement: horizon xPts above the 25th-percentile player at the same position.
- Attacking, clean-sheet, and bonus potential: the corresponding blended xPts components summed
  across the horizon.
- Differential potential: `100 - ownership percentage` before percentile normalization.
- Ceiling: maximum single-Gameweek xPts plus 25% of horizon attacking xPts. This is a transparent
  proxy until simulation produces empirical upper-tail outcomes.
- Consistency: inverse weekly xPts standard deviation, `1 / (1 + standard deviation)`.
- Rotation safety: expected minutes divided by 90, capped to zero through one.
- Injury safety: official chance of playing when supplied, otherwise a status-based fallback.
- Downside protection: a weighted combination of rotation safety, injury safety, and forecast
  confidence. Higher risk appetite makes this feature progressively neutral; it never rewards
  uncertainty directly.

Transfer reluctance is saved with the profile but deliberately has no effect on player ranking. It
will become an action threshold when transfer optimization is implemented.

## Normalization and scoring

Each raw feature is converted to a tie-aware percentile across the currently forecasted player
pool. Equal values receive equal average ranks. A feature with no variation receives a neutral 50.

Raw weights are normalized automatically:

```text
normalized weight_i = raw weight_i / sum(raw weights)

feature contribution_i = feature percentile_i * normalized weight_i

optimization score = sum(feature contributions)
```

Ownership preference is signed from -100 to +100. Negative values reward low-ownership players,
positive values reward highly owned players, and zero excludes ownership preference. Its absolute
value becomes its raw weight before all weights are normalized. The separate differential feature
can still be explicitly weighted.

The contribution table exposes the raw feature value, percentile, raw weight, normalized weight,
and resulting contribution. Contributions sum exactly to the displayed score.

## Known limitations

- Percentiles are relative to the current player pool, so a player's score can change when other
  players enter, leave, or receive new forecasts even if his own inputs do not change.
- Preset weights and the replacement percentile are product assumptions, not backtested optima.
- FPL fixture difficulty, current form, ownership, and status inherit the limitations and timing of
  the official data source.
- Ceiling and consistency are deterministic proxies; no outcome distribution or true variance is
  available before the simulation phase.
- Value is not a squad-level budget opportunity cost. Phase 5's constrained optimizer will decide
  whether a high-scoring combination is legal and affordable.
- A high score is not a BUY recommendation. Squad constraints, team context, transfer cost, hits,
  captaincy, and future flexibility are outside Phase 4.

The presets and feature definitions should be evaluated with time-ordered decision backtests before
being treated as performance-improving choices.
