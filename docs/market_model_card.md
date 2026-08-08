# Betting Market Forecast — Model Card

Model names: `market-fixture` and `market-xpts`  
Version: `0.3.0`  
Status: Phase 3 explainable baseline

## Intended use

This model converts optional pre-match bookmaker odds into fixture-level expected goals and an
independent player expected-points view. It is designed to complement the Phase 2 statistical
forecast, not to recommend bets or claim an advantage over bookmakers.

The app never requires a paid odds service. Odds can be entered manually or imported from a local
CSV file. Users are responsible for complying with the terms and licensing of their chosen source.

## Inputs and timing

Each covered fixture requires decimal odds for:

- 1X2: home win, draw, and away win
- Total goals 2.5: over and under
- An observation timestamp and bookmaker name

Every imported quote and forecast retains its observation, import, prediction, and input-cutoff
timestamps. Re-running an import with the same fixture, bookmaker, market, selection, and
observation timestamp is idempotent.

For time-ordered evaluation, only odds observed before the prediction cutoff should be used. The
current local workflow does not automatically distinguish a user's stale, closing, or
post-kickoff upload beyond its recorded timestamp.

## Method

1. Remove each bookmaker's overround independently. Multiplicative, power, and Shin de-vigging
   methods are available.
2. Take the median fair probability for each selection across bookmakers and normalize the
   resulting market. Median absolute deviation records disagreement as a dispersion measure.
3. Fit independent home and away Poisson goal rates to the consensus home/draw/away and over-2.5
   probabilities using bounded least squares.
4. Derive clean-sheet probabilities directly: home clean sheet is `exp(-away xG)` and away clean
   sheet is `exp(-home xG)`.
5. Allocate each team's implied goals to its players using expected minutes and shrunk historical
   goal and assist rates. Appearance, saves, bonus, and deductions retain the statistical model's
   transparent baseline assumptions.

The saved market xPts is independent of the statistical xPts. The display blend is:

```text
blended xPts = (1 - market weight) * statistical xPts
             + market weight * market xPts
```

The user controls market weight from 0% to 100%; the default is 30%. When a player/Gameweek has no
market forecast, blended xPts falls back to statistical xPts rather than treating missing coverage
as zero.

## Explainability

Fixture outputs expose fair 1X2 and over-2.5 probabilities, home and away xG, clean-sheet
probabilities, bookmaker count, dispersion, fit residual, de-vig method, and cutoff timestamp.
Player outputs retain component xPts plus the fixture venue, team and opponent xG, clean-sheet
probability, attacking shares, bookmaker count, and dispersion.

## Known limitations

- Independent Poisson goals do not model score correlation, game state, red cards, or team-specific
  finishing variance.
- 1X2 and totals odds may contain correlated bookmaker opinions; bookmaker count is not a count of
  independent models.
- The latest quote is selected per bookmaker and selection, so an incomplete or asynchronous feed
  can mix nearby observation times within a market.
- Team xG allocation does not use goalscorer, assist, anytime-scorer, penalty-taker, or lineup
  markets. Early-season player shares therefore depend heavily on positional priors.
- Current availability is reused across the forecast horizon, and late lineup or injury news is
  not inferred.
- The default 30% blend is a product setting, not a backtested optimum. No superiority over the
  statistical model or simpler baselines is claimed until time-ordered calibration and backtesting
  are implemented.

This output is for fantasy-football analysis and is not financial or gambling advice.
