# Current Team and Lineup Optimizer — Model Card

Optimizer name: `current-team-lineup`  
Version: `0.6.0`  
Status: Phase 6 deterministic baseline

## Intended use

This layer stores one local current FPL squad and recommends a starting XI, formation, captain,
vice captain, and bench order for the next Gameweek. It consumes forecasts but never changes them.

The current-team record includes all 15 players, purchase and selling prices, money in the bank,
free transfers, and availability flags for Wildcard, Free Hit, Bench Boost, and Triple Captain.
Manual entry and one-click import from the latest Phase 5 squad are supported. FPL Team ID import is
not yet implemented.

## Current-squad validation

Every saved team must contain 15 unique known players with exactly:

```text
2 goalkeepers
5 defenders
5 midfielders
3 forwards
maximum 3 players from one club
```

Purchase and selling prices must be positive, bank cannot be negative, and free transfers must be
between zero and five. Price and transfer fields are stored for Phase 7; they do not influence the
Phase 6 lineup decision.

## Starting XI

The engine evaluates all eight valid outfield formations:

```text
3-4-3  3-5-2  4-3-3  4-4-2
4-5-1  5-2-3  5-3-2  5-4-1
```

Each formation contains one goalkeeper and ten outfield players. For every position quota, players
are sorted primarily by next-Gameweek blended xPts, then expected minutes, lower risk, and stable
player ID. The legal formation with the greatest total next-Gameweek xPts is selected exactly.

Strategy utility is shown as context but does not determine the XI. This follows the design rule
that lineup selection should primarily optimize forecast points.

## Captain and vice captain

The recommended captain is the starter with the highest blended xPts. Captaincy adds that player's
xPts a second time to projected Gameweek points. The vice captain is the best different starter by
`xPts × expected-minutes availability`, with xPts and lower risk as tie-breakers.

Four transparent captaincy lenses are shown:

- Best expected: highest next-Gameweek blended xPts.
- Safest: xPts adjusted by expected minutes and downside risk.
- Highest ceiling: xPts plus attacking-component xPts as a temporary ceiling proxy.
- Best differential: xPts discounted by current ownership percentage.

The expected captain is the actual recommendation. The other three are comparison views, not
simultaneous recommendations.

## Bench order

The three non-starting outfield players are ordered by xPts, expected minutes, and lower risk. The
second goalkeeper is retained as the separate backup-goalkeeper slot and displayed fourth. Actual
FPL autosubstitution still depends on minutes played and formation legality after the deadline.

## Output interpretation and limitations

- Projected GW points are starting-XI xPts plus the captain's xPts one additional time.
- Next-3 and next-5 totals sum forecasts for all 15 squad members. They are not separately optimized
  future lineups and should not be interpreted as playable team points.
- Starting decisions use mean expected points. They do not simulate appearance failures,
  autosubs, correlated match outcomes, or outcome distributions.
- Ceiling, safety, and differential captain scores are transparent proxies and are not calibrated
  probabilities of a haul.
- Penalty duty, set pieces, confirmed lineups, late injury news, and effective ownership are not yet
  dedicated captain inputs.
- Chip availability is stored but chip use is not recommended in this phase.

Every lineup run stores its current team, forecast timestamp, market weight, strategy context, full
result, and creation time. Mathematical optimality means the XI maximizes the supplied mean xPts
within legal formations; it does not prove the forecasts or captain proxies are optimal.
