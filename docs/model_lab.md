# Model Lab

Release 8 adds an advanced, read-only workspace for inspecting the optimizer's model pipeline.
It is intended for users who want to audit assumptions and diagnostics; ordinary weekly decisions
remain in Weekly Dashboard.

## What it shows

- The latest cached statistical and market forecast timestamps
- A temporary 0–100% market blend with coverage and disagreement diagnostics
- Expected minutes, start probability, and forecast-confidence distributions
- Latest leakage-safe calibration/backtest results and recent run history
- Aggregate, decomposed feature influence for the active strategy profile
- Immutable statistical model versions, feature schemas, revisions, and safe parameters
- A local CSV export of the player-level diagnostic table

## Safety and behavior

The Model Lab only reads persisted model artifacts. Moving its blend slider recalculates a weighted
average of stored statistical and market xPts and recalculates the explainable strategy score. It
does not generate forecasts, run squad/lineup/transfer optimization, save a strategy, or modify the
sidebar's active market influence.

Runtime metadata is explicitly allow-listed. The page never displays or exports API keys,
credentials, database URLs, provider URLs, or local filesystem/cache paths. Model parameter keys
containing credential- or location-like terms are filtered before presentation.

## Interpreting the views

Market disagreement is a diagnostic, not proof that either source is correct. Missing market
coverage falls back to statistical xPts. Feature influence explains the post-forecast strategy
ranking and should not be interpreted as causal importance inside the statistical model.
Calibration remains advisory and depends on imported historical outcomes, adequate sample sizes,
and strictly pre-deadline forecasts.
