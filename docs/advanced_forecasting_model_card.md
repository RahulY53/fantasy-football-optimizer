# Advanced forecasting model card

## Scope

Phase 9 upgrades both sides of the forecast blend. The statistical model uses more official FPL
signals and a more empirical expected-minutes calculation. The market model can add BTTS, home and
away team totals, and individual anytime-goalscorer prices to the existing 1X2 and total-goals fit.
All additions are optional and preserve the Phase 2–3 fallback behavior.

## Improved expected minutes

The role estimate combines three sources:

- a weak position-and-price preseason prior;
- observed starts per team match;
- observed minutes as a share of the position's expected starter minutes.

Starts receive 70% and minutes share 30% of the empirical role signal. Three prior matches are
retained so small samples do not immediately force probabilities to zero or one. Start duration is
learned from observed minutes as starts accumulate. Residual minutes outside estimated starts are
used to estimate substitute involvement and are blended with a position prior.

Official injury status and chance of playing remain a hard availability cap. Expected minutes are
the probability-weighted sum of starting and substitute scenarios; 60-minute probability is
calculated separately for clean-sheet and appearance scoring.

## Additional official FPL statistics

Historical goal, assist, save, and bonus rates remain shrunk toward position priors over 900 prior
minutes. Phase 9 adds two bounded supporting adjustments:

- ICT per 90 and the difference between recent form and season points per game create an attacking
  multiplier limited to 0.85–1.15.
- BPS per 90 creates a bonus multiplier limited to 0.88–1.12.

These narrow bounds are intentional: ICT, form, BPS, goals, assists, and bonus overlap, so a large
adjustment would double-count the same past performance. The exact multipliers appear in each
fixture explanation. These are predictive heuristics, not calibrated causal effects.

## Advanced fixture markets

The core market forecast still requires complete bookmaker snapshots for:

- match result: home, draw, away;
- total goals 2.5: over, under.

When complete, the following two-way markets are independently de-vigged per bookmaker and then
added to the same two-parameter Poisson fit:

- both teams to score: yes, no;
- home team total 1.5: over, under;
- away team total 1.5: over, under.

For Poisson means `λh` and `λa`, the extra fitted probabilities are:

```text
P(BTTS) = (1 - exp(-λh)) × (1 - exp(-λa))
P(team over 1.5) = 1 - exp(-λ) × (1 + λ)
```

The least-squares residual now reports agreement across every available core and advanced target.
If an optional market is incomplete, it is excluded rather than blocking the fixture.

## Anytime-goalscorer odds

CSV rows use market `anytime_goalscorer`, selection `score`, and an official FPL `player_id`.
Latest prices are combined across bookmakers using the median raw implied probability. Because an
anytime-scorer feed normally supplies only the yes price, this probability cannot be de-vigged as a
standalone two-way market and should be interpreted cautiously.

For goal allocation, scorer probabilities are converted to Poisson scoring intensities with
`-log(1-p)`. The normalized scorer signal receives 50% weight and the existing shrunk statistical
goal share receives 50%. Unquoted players retain their statistical share, and all player weights
are normalized back to the team's fitted xG. Missing scorer prices therefore leave the baseline
allocation unchanged.

## Limitations

- Bootstrap data is season-aggregate data; it does not provide a true recent lineup/minutes history.
- ICT, form, and BPS adjustments are bounded heuristics and require backtesting in Phase 12.
- The independent-Poisson model does not capture score dependence, tactical game state, or player
  correlations.
- Team-total 1.5 is the only team line supported in Phase 9.
- Goalscorer yes-only prices contain bookmaker margin. Their normalized allocation is useful, but
  the displayed raw probability is not a fully fair probability.
- Market coverage can be sparse and forecasts can become stale. Every output stores its cutoff and
  should be regenerated after material odds, injury, or lineup news.
