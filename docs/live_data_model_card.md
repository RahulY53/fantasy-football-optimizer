# Live team import and live odds model card

## Public FPL team import

My Team accepts a positive public FPL Team ID. The backend determines the latest published
Gameweek from `bootstrap-static` and the entry response, then requests entry details, picks,
history, and transfers. Picks are joined to local players exclusively through official FPL element
IDs. Names are never used as player identity.

The imported 15 players replace the local **My Team** squad, so the existing lineup, transfer,
multi-Gameweek, simulation, and chip services can consume them without optimizer changes. The
published XI, captain, vice captain, and bench order are stored separately from subsequently
optimized recommendations.

Public endpoints normally expose the last published Gameweek squad. They may omit transfers made
after the deadline, while free-transfer and chip state are not reliably public. The UI therefore
labels imports **Published GW Squad**, shows the refresh timestamp, and treats free transfers and
chip availability as unknown assumptions that the user can edit. No password or authenticated FPL
session is requested or stored.

## Odds-API.io integration

The optional connector uses server-side Odds-API.io v3 endpoints for pending football events in
the `england-premier-league` league and multi-event odds. Credentials are read from
`FPL_OPTIMIZER_ODDS_API_KEY`; the key is never included in cache keys, database rows, UI responses,
or source code. Manual and CSV providers remain supported.

Only complete bookmaker-level 1X2 and over/under 2.5 markets enter the existing market pipeline.
Each bookmaker is persisted independently as immutable `OddsSnapshot` rows. The existing model
removes each bookmaker's margin before taking median fair-probability consensus and fitting
Poisson market expected goals. New prices then rebuild market and player xPts; strategy weights
remain separate.

## Fixture matching and freshness

Vendor events must match both canonicalized home/away clubs and kickoff time. Configured aliases
cover common EPL variants. Confidence assigns 70 points to the two-team match, up to 25 for kickoff
proximity, and 5 for Premier League identity. Scores below 85 or ambiguous best matches are
rejected and reported rather than attached silently.

Normal requests use a one-hour disk cache by default. Provider failure falls back to the newest
valid cache. If no cached live data exists, manual/CSV odds remain available; if no markets exist,
forecast consumers use statistical xPts. The UI labels market data stale after two hours by
default. Every persisted snapshot carries its observed time. Prices observed by the corresponding
FPL deadline receive the `pre_deadline` label and backtests still enforce their forecast and input
cutoff timestamps.

## One-action update

**Update my team** refreshes official data through its cache policy, force-refreshes the public
squad, regenerates six-Gameweek statistical forecasts, refreshes odds where configured, rebuilds
market forecasts, and runs the existing lineup and transfer optimizers. Live-odds failure is a
non-fatal warning and the statistical-only workflow continues.

## Limitations

- Odds availability, bookmaker names, market shapes, and quotas depend on the provider account.
- Public FPL data cannot guarantee the user's unpublished post-deadline squad.
- Purchase and selling values are those published in the picks response when present.
- The app does not automate private FPL authentication or transfer execution.
- Market movement is retained in snapshots but the current UI focuses on latest consensus rather
  than a full intraday movement chart.
