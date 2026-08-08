# 2026/27 Statistical xPts — Model Card

Model name: `advanced-statistical-xpts`
Version: `1.0.0`
Status: 2026/27 rules-complete expected-points baseline

## Intended use

This model provides an auditable statistical expected-points baseline for the next six FPL
Gameweeks. It supports player browsing and future comparison against the betting-market model.
It is not yet transfer, captain, chip, or squad advice.

## Inputs

- Official FPL player status, chance of playing, price, minutes, starts, goals, assists, saves,
  bonus, cards, penalties, own goals, CBI, tackles, recoveries, and defensive contributions
- Official team home/away attack and defence ratings when populated
- Official FPL fixture difficulty as a fallback
- Future fixture assignments, including blanks and doubles
- A timestamped official-data cutoff

## Expected minutes

Expected minutes are a probability-weighted mixture of starting and substitute scenarios.
Observed starts replace a three-match prior as the season progresses. Before meaningful lineup
history exists, price within each position acts as a weak role prior. Official availability caps
all appearance scenarios.

Confidence is low with fewer than five team matches, medium before twelve matches, and high
afterwards unless availability is ambiguous.

## Expected points

Each fixture is calculated separately and then summed into its FPL Gameweek:

```text
statistical xPts = appearance
                 + goal points
                 + assist points
                 + clean-sheet points
                 + save points
                 + defensive-contribution points
                 + bonus points
                 + expected deductions
```

Goal, assist, save, and bonus rates are shrunk toward position priors using 900 prior minutes.
Events reported with zero official minutes are ignored as an upstream data-quality safeguard.
Fixture attack is adjusted using official team ratings, with FPL difficulty as the fallback.
Clean-sheet probability uses a simple Poisson opponent-goal baseline. Goal points use the 2026/27
position values: goalkeeper 10, defender 6, midfielder 5, and forward 4.

Save points use the actual one-point-per-three-saves threshold under a Poisson count model.
Defensive contributions use the official match thresholds and two-point cap: defenders require 10
combined clearances, blocks, interceptions, and tackles; midfielders and forwards require 12 of
those actions plus recoveries. Season action rates are shrunk toward position priors and converted
to the probability of reaching the relevant threshold in each appearance scenario.

Penalty saves add five points. Expected yellow cards, red cards, own goals, penalty misses, and
goals-conceded bands are included as explicit deductions from their shrunk historical rates.

## Known limitations

- Preseason expected minutes are role priors, not predicted lineups.
- Official FPL strengths can be missing or uncalibrated early in the season.
- The baseline does not yet consume player xG/xA, recent match-by-match minutes, tactical roles,
  set pieces, manager quotes, or external injury reports.
- Defensive actions are season aggregates rather than match-by-match distributions; the Poisson
  threshold forecast is explainable but requires ongoing calibration.
- Bonus uses historical bonus and BPS rates. It does not reproduce every event in the updated
  2026/27 Bonus Points System.
- Availability for later Gameweeks reuses the current status; recovery timelines are not inferred.
- The model is not claimed to outperform simpler baselines until time-ordered backtesting exists.

Every saved forecast includes its model version, prediction time, input cutoff, confidence,
component totals, appearance probabilities, fixture adjustments, and this limitation context.
