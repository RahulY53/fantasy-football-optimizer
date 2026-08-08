# Transfer optimizer model card

## Purpose

Phase 7 answers one immediate decision: should the saved FPL team roll its transfer, make the best
one-transfer move, or make the best two-transfer move? It compares all three choices from the same
forecast timestamp, strategy profile, market blend, current squad, selling prices, bank, and free
transfer count. Every evaluation is saved locally for reproducibility.

## Optimization

The optimizer solves a separate binary mixed-integer program for exactly one and exactly two
transfers. Rolling is the unchanged squad. Every final squad must contain 15 players with exactly
2 goalkeepers, 5 defenders, 5 midfielders, and 3 forwards, and no club may supply more than 3
players. An exact `k`-transfer plan retains exactly `15 - k` current players.

The primary objective is the sum of every selected player's blended expected points over the
chosen one-to-six-Gameweek horizon. Strategy utility is multiplied by a tiny constant and used only
as a deterministic tie-breaker between effectively equal xPts solutions. A still smaller player
ordering term makes repeated runs stable.

The budget constraint values retained current players at their saved selling prices and new players
at their current FPL purchase prices:

```text
cost(retained players at selling price) + cost(new players at buy price)
    <= current bank + value(all current players at selling price)
```

Ending bank is current bank plus proceeds from outgoing players minus the cost of incoming players.

## Comparison and recommendation

For each feasible plan:

```text
gross gain = final squad horizon xPts - current squad horizon xPts
hit cost   = 4 × max(0, transfers made - free transfers)
net gain   = gross gain - hit cost
```

The best non-zero plan is compared with a transfer-flexibility threshold:

```text
roll flexibility value = 0.5 + 0.025 × transfer reluctance
```

Transfer reluctance ranges from 0 to 100, so the threshold ranges from 0.5 to 3.0 projected points.
The optimizer recommends a transfer only when its net gain is strictly greater than that threshold;
otherwise it recommends rolling. This preference changes only the final decision threshold, not any
player forecast.

## Inputs and interpretation

- Statistical or blended player xPts generated before the evaluation
- The active strategy's planning horizon and tie-break utility
- The saved 15-player squad, individual selling prices, bank, and free transfers
- Current player buy prices, positions, and clubs from the official FPL snapshot

The reported gain is a model estimate versus holding the same squad. It is not a guarantee of
realized FPL points.

## Limitations

- The objective sums all 15 squad members, so it can overvalue bench points. It does not simulate
  the best starting XI and captain for every future Gameweek.
- Prices, player availability, forecasts, and the squad are static through the selected horizon.
- Selling prices are user-entered and are not reconstructed from FPL purchase-price rules.
- Phase 7 evaluates at most two immediate transfers. It does not plan a multi-week transfer path or
  model the accumulation and expiry of future free transfers.
- Chips, future hits, fixture postponements after the forecast cutoff, and rival behavior are not
  simulated.
- The roll-flexibility threshold is a transparent heuristic and has not yet been empirically
  calibrated. Phase 8 can replace it with a multi-period planner.
