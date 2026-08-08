# Multi-Gameweek planner model card

## Purpose

Phase 8 builds one connected plan across two to six future Gameweeks. It decides when to roll or
spend transfers, which players to buy and sell, the legal starting XI and formation each week, and
the captain. This differs from repeatedly choosing the best immediate transfer because later
fixtures and free-transfer carry are included in the same objective.

## Decision model

The planner is a binary mixed-integer program solved with SciPy's HiGHS backend. For every player
and Gameweek it has decisions for squad membership, starting-XI membership, captaincy, transfer in,
and transfer out. A separate state/action representation tracks the number of free transfers
available and zero, one, or two transfers made that week.

Every weekly squad must contain exactly 2 goalkeepers, 5 defenders, 5 midfielders, and 3 forwards,
with no more than 3 players from one club. The starting XI contains exactly 1 goalkeeper, 3–5
defenders, 2–5 midfielders, and 1–3 forwards. Exactly one starter is captain.

The weekly projected score is:

```text
lineup xPts + captain xPts - 4 × max(0, transfers - free transfers)
```

The primary objective maximizes the sum of these hit-adjusted scores across the horizon. The active
strategy utility is used only as a very small terminal-squad tie-breaker. An even smaller timing
tie-breaker delays a transfer when making it earlier produces exactly the same projected score,
preserving real-world flexibility.

## Free transfers and money

Free transfers evolve after every planned deadline:

```text
next free transfers = min(5, max(0, available - transfers made) + 1)
```

The initial state comes from My Team. Each weekly action is explicitly linked to its available-free-
transfer state, so hits and carry are internally consistent throughout the path.

The bank is checked after every Gameweek. Current players use their saved selling prices. Players
bought during the plan use their current FPL price for both buying and any later sale because Phase
8 does not forecast price changes.

## Candidate shortlist

To keep a six-Gameweek solve responsive on a local desktop, the planner includes all 15 current
players and the strongest 35 non-current alternatives at each position, ranked by total horizon
xPts, peak weekly xPts, then strategy utility. The mixed-integer result is exact within this
disclosed shortlist, not necessarily across every registered FPL player. Phase 7 remains the
full-pool exact immediate-transfer comparison.

## Outputs and persistence

Every run stores the forecast timestamp, strategy, market blend, starting bank and free transfers,
full weekly path, hits, and projected scores. The interface displays each week's transfers, bank,
free-transfer transition, formation, XI, captain, and gross and net points.

## Limitations

- Forecasts and prices are static snapshots. Re-run the planner after each deadline and material
  injury, schedule, odds, or price update.
- At most two transfers may be scheduled in one Gameweek. Wildcards and Free Hits are Phase 11.
- The model maximizes expected points and does not yet simulate outcome distributions, correlation,
  autosubs, vice-captain activation, or uncertainty scenarios. Simulation belongs to Phase 10.
- There is no explicit value for money left in the bank or unused free transfers after the final
  Gameweek, except where they help projected points inside the horizon.
- Selling prices for the current squad depend on user-entered values. Future sale prices assume no
  price movement.
- The candidate shortlist can exclude a low-ranked player whose unusual price or fixture pattern
  would have been useful in the globally unrestricted solution.
