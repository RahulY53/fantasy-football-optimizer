# Monte Carlo simulation model card

## Purpose

Phase 10 turns point forecasts into ranges for the saved current team. It answers questions such as
how wide the likely score distribution is, how much downside a correlated defensive stack carries,
and which selected players have the greatest blank or haul probability. It does not replace xPts;
the simulation is conditional on the current advanced statistical/market blend.

## Scenario and decisions

The baseline scenario holds the current 15-player squad throughout a one-to-six-Gameweek horizon.
Before drawing outcomes, the engine selects the highest-xPts legal formation and starting XI for
each Gameweek from all eight valid FPL formations. The highest-xPts starter is captain and receives
a second simulated score. These decisions are fixed across iterations, avoiding hindsight lineup
selection after outcomes are known.

Between 1,000 and 50,000 iterations are supported. Every run stores its integer seed; identical
inputs and seed reproduce exactly the same result.

## Component simulation

Each player/Gameweek uses the component forecasts produced by Phase 9:

- Appearance uses a categorical no-appearance, under-60, or 60-plus draw derived from appearance
  and 60-minute probabilities. It is scaled to preserve the forecast appearance expectation.
- Goals and assists use Poisson draws. Their unconditional xPts are converted to conditional rates
  for an appearing player.
- Clean-sheet points use a Bernoulli threshold whose expectation matches the clean-sheet component.
- Save points and negative deductions use Poisson approximations.
- Bonus uses a Poisson approximation capped at three points.

The simulation mean should stay close to component xPts, but will not match exactly because official
FPL scoring has discrete interactions and the simplified bonus cap changes high-tail behavior.

## Dependence

Treating every player independently understates the risk of stacking teammates. Phase 10 adds two
shared club/Gameweek variables:

- A mean-one lognormal attacking shock with sigma 0.25 multiplies every teammate's goal and assist
  rate in the same iteration.
- One shared uniform clean-sheet draw is compared with each eligible teammate's threshold, creating
  positively correlated defensive returns while retaining player-specific 60-minute exposure.

Opposing-team, match-score, assister/scorer, and bonus correlations are not yet modeled explicitly.

## Reported outputs

The saved result contains:

- horizon mean, median, standard deviation, P10, P25, P75, and P90;
- probabilities of scoring below 40 points per Gameweek or at least 50/60 per Gameweek;
- a compact total-points histogram;
- weekly formation, captain, expected xPts, simulated mean, P10/P90, and 40-plus probability;
- selected-player contribution distributions and horizon probabilities of no more than 2 points,
  at least 5 points, and at least 10 points. Captain contributions include the doubled score.

## Limitations

- The scenario holds the current squad. It does not yet simulate the latest Phase 8 transfer path.
- Autosubs, vice-captain activation, chips, red-card suspension effects, and future injuries are not
  modeled.
- Double Gameweeks are aggregated from component expectations; their within-week dependence is only
  approximated.
- Save, bonus, card, and deduction distributions are moment-matching approximations rather than a
  full event-by-event match engine.
- Shared club shocks are transparent assumptions, not empirically calibrated parameters. Phase 12
  should calibrate dispersion, component distributions, coverage, and probability reliability.
- Results are conditional on forecast quality and are not guarantees or betting probabilities.
