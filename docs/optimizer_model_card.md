# Initial Squad Optimizer — Model Card

Optimizer name: `initial-squad-milp`  
Version: `0.5.0`  
Solver backend: SciPy MILP / HiGHS  
Status: Phase 5 deterministic baseline

## Intended use

The optimizer chooses the highest-utility legal initial FPL squad from currently forecasted
players. Its objective uses the active Phase 4 strategy score. It does not predict player outcomes,
change expected points, or claim the resulting squad will outperform another squad.

## Mathematical formulation

For every candidate player `i`, define a binary decision variable:

```text
x_i = 1 when player i is selected, otherwise 0
```

The primary objective is:

```text
maximize sum(x_i * optimization_score_i)
```

A very small expected-points term and stable player-order term break exact utility ties. They are
several orders of magnitude smaller than the strategy score and are not reported as part of the
strategy objective.

The model enforces:

```text
sum(x_i) = 15
sum(x_i for GK) = 2
sum(x_i for DEF) = 5
sum(x_i for MID) = 5
sum(x_i for FWD) = 3
sum(x_i for each club) <= 3
sum(x_i * price_i) <= available budget
```

Locked or must-buy players receive `x_i = 1`; excluded players receive `x_i = 0`. Inputs are
validated before solving so a player cannot be both locked and excluded, locked quotas cannot
already violate position or club limits, and unknown player IDs are rejected.

## Solver choice

The implementation uses SciPy's open-source MILP interface with the HiGHS backend. SciPy was
already a project dependency, so this provides a local zero-cost binary integer program without an
additional runtime installation. The solver is isolated behind framework-independent records and a
single optimizer function, allowing a future PuLP or OR-Tools backend without changing the UI,
forecast, or strategy layers.

Successful runs are revalidated independently after solving and persisted with the full strategy,
market weight, budget, lock/exclusion constraints, solver identity, objective, and selected players.

## Output interpretation

- Strategy objective is the sum of the 15 selected optimization scores.
- Projected xPts is the sum of player forecasts over the strategy horizon. It is shown for context,
  but the strategy objective—not pure xPts—is optimized.
- Remaining budget is available budget minus current purchase prices.
- Average ownership and risk describe the selected group; they are not additional constraints.

## Known limitations

- This is a fresh initial squad, not a transfer recommendation for an existing team.
- It selects 15 players but does not choose a starting XI, formation, captain, vice-captain, or
  bench order; those belong to Phase 6.
- Purchase prices use the latest official FPL snapshot. Selling value, bank, price changes, and
  current-team purchase prices are outside this phase.
- The model is deterministic and does not account for correlated team outcomes or simulated squad
  variance.
- Preset and custom strategy utilities have not yet been validated by time-ordered decision
  backtests. Mathematical optimality only means no feasible squad has a higher stated objective.
- Locking players can make a solve infeasible through combined budget or quota effects even if each
  locked player is individually valid.

The squad should therefore be treated as the exact optimum for the supplied inputs and preferences,
not proof that those inputs or preferences are themselves optimal.
