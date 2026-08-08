# Backtesting and calibration model card

## Purpose

Phase 12 measures historical point forecasts against final player/Gameweek outcomes and estimates
whether the statistical/market blend should receive more or less market influence. It is an
evaluation tool, not an automatic model-training or settings-update system.

## Required data

The importer accepts UTF-8 CSV with these required columns:

- `player_id`: official FPL player ID already present in the local database
- `gameweek`: official FPL Gameweek number already present locally
- `actual_points`: final FPL points for that player in the whole Gameweek

Optional columns are `actual_minutes`, `goals`, `assists`, `clean_sheets`, `saves`, `bonus`, and an
ISO-8601 `finalized_at` timestamp. A player/Gameweek pair is unique. The entire file is validated
before any row is stored; a later import updates an existing pair.

## Leakage protection

For every outcome, the evaluator selects the latest statistical forecast satisfying both:

```text
prediction_at <= Gameweek deadline
input_cutoff_at <= Gameweek deadline
```

Market forecasts use the same conditions. Forecasts produced or sourced after the deadline are
excluded. Missing market coverage falls back to statistical xPts, matching the live blend.

## Calibration and evaluation

The evaluator searches market weights from 0% to 100% in 10-point increments and minimizes RMSE.
With at least four Gameweeks, the earliest 70% select the weight and the remaining later Gameweeks
form a chronological holdout. No player rows from a Gameweek are split across those sets.

With fewer than four Gameweeks, all rows are used for both selection and reporting. The result is
labeled `exploratory in-sample` and should not be treated as evidence of future improvement.

Reported point metrics are mean absolute error (MAE), root mean squared error (RMSE), signed bias
(`prediction - actual`), and Pearson correlation when defined. The selected blend is also broken
down by position and predicted-xPts calibration band. When actual minutes are imported, the same
error metrics compare expected with realized minutes.

## Interpretation and limitations

- Lower MAE and RMSE are better.
- Positive bias means forecasts were too high; negative bias means they were too low.
- Correlation measures ranking agreement, not calibration.
- Market-only accuracy covers only observations with market forecasts. Blend accuracy includes
  every observation and falls back to statistical xPts where markets are absent.
- Results depend on accurate outcomes and timestamp history. The current release evaluates
  Gameweek totals, uses coarse global weights, and does not correct missing-market selection bias.

Phase 12 never changes the sidebar's Market influence control or any stored strategy.
