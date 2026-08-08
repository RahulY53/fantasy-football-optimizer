# Basic Statistical xPts — Model Card

Model name: `basic-statistical-xpts`  
Version: `0.2.0`  
Status: Phase 2 explainable baseline

## Intended use

This model provides an auditable statistical expected-points baseline for the next six FPL
Gameweeks. It supports player browsing and future comparison against the betting-market model.
It is not yet transfer, captain, chip, or squad advice.

## Inputs

- Official FPL player status, chance of playing, price, minutes, starts, goals, assists, saves,
  and bonus
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
                 + bonus points
                 + expected deductions
```

Goal, assist, save, and bonus rates are shrunk toward position priors using 900 prior minutes.
Events reported with zero official minutes are ignored as an upstream data-quality safeguard.
Fixture attack is adjusted using official team ratings, with FPL difficulty as the fallback.
Clean-sheet probability uses a simple Poisson opponent-goal baseline.

## Known limitations

- Preseason expected minutes are role priors, not predicted lineups.
- Official FPL strengths can be missing or uncalibrated early in the season.
- The baseline does not yet consume player xG/xA, recent match-by-match minutes, tactical roles,
  penalties, set pieces, manager quotes, or external injury reports.
- Bonus, cards, saves, and goals-conceded deductions are deliberately simple expectations.
- Availability for later Gameweeks reuses the current status; recovery timelines are not inferred.
- The model is not claimed to outperform simpler baselines until time-ordered backtesting exists.

Every saved forecast includes its model version, prediction time, input cutoff, confidence,
component totals, appearance probabilities, fixture adjustments, and this limitation context.

