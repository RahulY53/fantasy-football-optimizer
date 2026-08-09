# Fantasy Premier League Optimizer

An open-source, local-first forecasting and decision engine for Fantasy Premier League managers.
It combines official FPL data, explainable expected-points models, optional bookmaker signals,
constrained optimization, simulation, and historical evaluation in a Streamlit application with
an optional FastAPI interface.

The application is designed for power users who want transparent assumptions, reproducible
outputs, and control over their own data. Successful downloads are cached locally, forecasts and
model metadata are timestamped, and normal use does not require a hosted account or cloud database.

## What the application can do

### Official FPL data and live team import

- Download players, clubs, Gameweeks, fixtures, availability, prices, ownership, form, transfers,
  and current-season performance from the public FPL service.
- Store immutable source snapshots and normalized records in SQLite.
- Reuse the latest successful cache when the live service is temporarily unavailable.
- Import a publicly visible FPL squad from its Team ID, including published picks, captaincy,
  selling prices, bank, manager summary, recent history, and transfers where available.
- Preserve full official player names throughout search, saved teams, analytics, forecasts, and
  historical evaluation, with web-name and accent-insensitive search fallbacks.

### Player forecasting

- Generate versioned statistical forecasts for up to six upcoming Gameweeks.
- Estimate probability-weighted expected minutes from starts, minutes share, role, availability,
  and substitute scenarios.
- Model appearance, goals, assists, clean sheets, saves, bonus, deductions, and defensive
  contributions using the 2026/27 FPL scoring rules.
- Handle single, double, and blank Gameweeks.
- Use team strength, fixture difficulty, home/away context, form, ICT, BPS, and bounded player
  signals while retaining component-level explanations.
- Show next-Gameweek and multi-Gameweek xPts, opponent context, start probability, confidence, and
  source cutoff timestamps.

### Betting-market integration

- Import 1X2, over/under 2.5, both-teams-to-score, team totals, and goalscorer information.
- De-vig bookmaker prices and estimate expected goals, clean-sheet probabilities, market
  dispersion, fit residuals, and consensus quality.
- Produce independent fixture and player market forecasts.
- Blend statistical and market xPts from 0–100%, falling back to statistical forecasts where
  market coverage is missing.
- Refresh supported live odds through Odds-API.io or import odds manually through CSV and forms.
- Retain cached market snapshots when a provider is unavailable.

### Strategy and explainability

- Use Balanced, Conservative, Aggressive, Value Hunter, Differential, or custom profiles.
- Configure planning horizon, risk appetite, transfer reluctance, ownership preference, and
  feature weights.
- Score expected points, fixtures, minutes, form, value, value over replacement, attacking and
  defensive potential, bonus, ceiling, consistency, rotation safety, injury safety, and
  differential appeal.
- Inspect normalized weights and the exact contribution of every feature to every player score.
- Save named strategy profiles locally without altering the underlying forecasts.

### Squad, lineup, and transfer optimization

- Construct an optimal legal 15-player squad with the required positional quotas, a configurable
  budget, no more than three players per club, and optional player locks or exclusions.
- Save or edit the current squad with purchase prices, selling prices, bank, free transfers, and
  chip availability.
- Select the strongest legal starting XI, formation, ordered bench, captain, and vice-captain.
- Compare rolling against the best exact one- and two-transfer plans.
- Account for selling prices, available bank, free transfers, four-point hits, transfer reluctance,
  squad legality, projected gain, and future flexibility.
- Preserve reproducible solver inputs and constraint audits for saved optimization runs.

### Multi-Gameweek planning

- Optimize a connected two-to-six-Gameweek transfer path instead of treating each week in
  isolation.
- Jointly reason about transfers, squad composition, formation, starting XI, captaincy, bank, and
  free-transfer state.
- Compare immediate returns with longer fixture swings and the value of rolling.
- Display weekly decisions, projected points, transfer costs, and the resulting squad path.

### Simulation and uncertainty

- Run 1,000–50,000 reproducible Monte Carlo simulations for the current squad.
- Model player appearance, attacking returns, clean sheets, saves, bonus, deductions, and
  defensive contributions.
- Apply correlated team- and match-level shocks so teammates are not treated as independent.
- Report means, medians, P10/P90 ranges, distributions, blank probabilities, return probabilities,
  haul probabilities, and player-level outcome summaries.
- Use explicit seeds so equivalent simulation inputs can be reproduced.

### Chip planning

- Evaluate Wildcard, Free Hit, Bench Boost, and Triple Captain opportunities across up to six
  Gameweeks.
- Optimize temporary or permanent squads, legal lineups, and captains for the relevant chip.
- Compare projected chip gain, recommended timing, squad changes, and current availability.
- Respect the current squad's selling value plus bank.

### Historical evaluation and calibration

- Import final player/Gameweek outcomes from CSV with atomic validation.
- Match outcomes only to forecasts whose prediction time and input cutoff preceded the official
  deadline.
- Use chronological calibration and holdout windows to reduce information leakage.
- Compare statistical, market, and blended MAE, RMSE, bias, correlation, positional accuracy,
  calibration bands, and expected-minutes error.
- Inspect blend-weight curves and retain recent evaluation summaries without automatically changing
  live settings.

### Player analytics

- Filter the player universe by name, team, position, price, ownership, expected minutes, xPts,
  risk, and strategy score without regenerating forecasts.
- Compare two to five players in raw tables and position-aware radar charts.
- Plot configurable 2×2 decision matrices with selectable populations, reference lines, quadrant
  explanations, and presets for value, threat, minutes, ownership, and market disagreement.
- Compare weekly and cumulative forecast paths, attacking and defensive fixture difficulty, and
  component-level projections.
- Send selections from the player explorer, decision matrix, current squad, or optimized squad into
  the same comparison workspace.
- Export analytics, forecast comparisons, changes, and diagnostics to CSV.

### Watchlist and change detection

- Maintain a persistent local player watchlist with personal notes.
- Combine watchlist membership with the normal analytics filters and comparison workflow.
- Compare the latest two official-data, statistical-forecast, market-forecast, and availability
  snapshots.
- Surface meaningful movements in xPts, expected minutes, price, ownership, market projections,
  player status, and news.

### Weekly decision dashboard

- Refresh live evidence or explicitly reuse the current cache.
- Combine optimized lineup, captaincy, transfer alternatives, future planning, simulation, and chip
  analysis into one decision card.
- Explain the recommendation, confidence, key risks, transfer path, scenario uncertainty, and data
  freshness.
- Keep the underlying engines distinct so conflicting evidence remains visible.

### Model Lab

- Inspect immutable model names, semantic versions, feature schemas, code revisions, safe
  parameters, and forecast-row counts.
- Test temporary statistical/market blend weights without changing active settings.
- Explore expected-minutes distributions, market coverage, model disagreement, calibration,
  backtests, and aggregate strategy feature influence.
- Export player-level model diagnostics.
- Explicitly exclude credentials, URLs, database connections, and local filesystem paths from the
  displayed settings and exports.

### What-if analysis

- Override a player's start probability or mark one or more players unavailable.
- Adjust a club's attacking environment while leaving defensive forecast components unchanged.
- Protect current players from sale, force a sale, force a purchase, or exclude transfer targets.
- Force Wildcard, Free Hit, Bench Boost, or Triple Captain timing within the selected horizon.
- Re-score temporary assumptions and run the existing exact transfer and chip solvers.
- Compare baseline and scenario decisions, squad xPts, transfer alternatives, forced-chip value,
  and player-level forecast sensitivity.
- Keep every scenario session-only; forecasts, team state, strategies, and normal run history are
  not modified.

## Typical workflow

1. Refresh official FPL data.
2. Generate forecasts from the sidebar.
3. Optionally import or refresh bookmaker odds and choose market influence.
4. Select or customize a strategy.
5. Import the current FPL team or build an optimized initial squad.
6. Optimize the next lineup and captaincy.
7. Compare transfers and inspect the future planning path.
8. Run simulations and evaluate chip opportunities.
9. Use Weekly Dashboard for the consolidated decision.
10. Use Player Analytics, Model Lab, and What-if Analysis when deeper investigation is needed.

Every workspace can also be used independently when its required data is available.

## Installation

Requirements:

- Python 3.12 or newer
- Git

Create an environment, install the project, initialize the database, and start Streamlit:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
streamlit run frontend/streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501).

On first run, use **Refresh FPL data** and then **Generate advanced forecasts** in the sidebar.

## Configuration

Settings use the `FPL_OPTIMIZER_` prefix and can be placed in a local `.env` file. The `.env` file,
SQLite runtime files, and response caches are excluded from Git.

| Setting | Purpose | Default |
|---|---|---|
| `FPL_OPTIMIZER_DATABASE_URL` | SQLAlchemy database connection | `sqlite:///data/fpl_optimizer.db` |
| `FPL_OPTIMIZER_CACHE_DIR` | Provider-response cache directory | `data/cache` |
| `FPL_OPTIMIZER_CACHE_TTL_SECONDS` | Official-data cache lifetime | `900` |
| `FPL_OPTIMIZER_HTTP_TIMEOUT_SECONDS` | Provider request timeout | `15` |
| `FPL_OPTIMIZER_LOG_LEVEL` | Application logging level | `INFO` |
| `FPL_OPTIMIZER_ODDS_API_KEY` | Optional server-side Odds-API.io credential | unset |
| `FPL_OPTIMIZER_ODDS_API_BASE_URL` | Odds provider endpoint | provider default |
| `FPL_OPTIMIZER_ODDS_BOOKMAKERS` | Requested bookmaker list | `Bet365,Unibet,Pinnacle` |
| `FPL_OPTIMIZER_ODDS_CACHE_TTL_SECONDS` | Odds response cache lifetime | `3600` |
| `FPL_OPTIMIZER_ODDS_STALE_AFTER_SECONDS` | Live-odds freshness threshold | `7200` |

The odds credential is used only by the backend and is not stored in SQLite. Provider account
coverage and accepted bookmakers can vary by region and subscription; a rejected live request does
not prevent manual odds import or statistical-only operation.

## Docker

Build and run the Streamlit application with a persistent data volume:

```bash
docker compose up --build
```

Start the optional API as well:

```bash
docker compose --profile api up --build
```

Streamlit is exposed on port `8501`; the API is exposed on port `8000` when enabled.

## Local API

Start the API directly with:

```bash
uvicorn api.main:app --reload
```

Interactive OpenAPI documentation is available at
[http://localhost:8000/docs](http://localhost:8000/docs).

Endpoint groups include:

- Health and data: `/health`, `/data/fpl/refresh`, `/players`, `/fixtures`
- Forecasts and markets: `/forecasts/statistical`, `/forecasts/advanced`, `/markets`
- Strategy and squads: `/strategy/presets`, `/strategy/score`, `/strategies`,
  `/optimizer/squad`
- Current team and lineup: `/team/current`, `/team/current/lineup`, `/team/import`
- Decisions: `/transfers/evaluate`, `/planner/run`, `/simulation/run`, `/chips/evaluate`
- Evaluation: `/backtesting/outcomes/import`, `/backtesting/run`
- Live odds: `/odds/live/status`, `/odds/live/test`, `/odds/live/refresh`

The Streamlit application currently contains additional interactive analytics, dashboard, model,
and scenario workspaces that are not exposed as API endpoints.

## Architecture

```text
frontend/                 Streamlit pages and shared presentation helpers
api/                      Optional FastAPI transport
fpl_optimizer/
  analytics/              Cached player datasets, filters, comparisons, and matrices
  backtesting/            Outcome parsing, calibration, and evaluation
  data/                    Provider clients, cache, schemas, and team import
  database/                SQLAlchemy models and repositories
  domain/                  Framework-independent records
  features/                Expected-minutes and fixture-strength features
  forecasting/             Statistical and market projection logic
  odds/                    Odds normalization, consensus, and providers
  optimizer/               Squad, lineup, transfer, planner, and chip solvers
  scoring/                 Strategy presets, normalization, and decomposition
  services/                Application orchestration
alembic/                   SQLite-compatible schema migrations
tests/                     Unit and integration coverage
docs/                      Model cards and workflow documentation
```

The core models and solvers are independent of Streamlit and FastAPI. Services coordinate
transaction boundaries, repositories own persistence, and adapters format the results for users.

## Development and verification

Run the complete local checks before opening a pull request:

```bash
pytest
ruff check .
mypy fpl_optimizer
```

The test suite covers forecasting components, scoring, legal squad and lineup constraints,
transfer rules and hits, planning, simulation reproducibility, chips, historical leakage controls,
analytics, watchlists, change detection, weekly decisions, Model Lab safety, and scenario behavior.

## Documentation

Detailed methodology and limitations are maintained in `docs/`, including:

- Statistical and advanced forecasting model cards
- Market forecast methodology
- Strategy-score explainability
- Squad, lineup, transfer, planner, simulation, and chip models
- Historical evaluation and leakage controls
- Player naming, analytics, comparisons, matrices, watchlists, and change detection
- Weekly decision dashboard
- Model Lab
- What-if analysis

`DESIGN.md` contains the broader architecture, modeling assumptions, and major design decisions.

## Data, privacy, and security

- Application data stays in the configured local database and cache unless the user explicitly
  calls an external provider.
- API keys belong in `.env` or process environment variables, never in source files.
- The repository ignores `.env`, database files, write-ahead logs, and caches.
- Model Lab exposes only allow-listed settings and filtered model parameters.
- CSV exports are created locally in the user's browser session.
- The public FPL API is undocumented; users should respect its applicable terms and should not
  assume that downloaded data can be redistributed.

## Known limitations

- Forecasts, simulations, and optimizer outputs are estimates rather than guarantees.
- Live bookmaker coverage depends on provider availability, region, account permissions, and market
  support.
- Historical calibration quality depends on sufficient final outcomes and genuinely pre-deadline
  forecast snapshots.
- What-if start assumptions use an explicit starter/substitute minutes approximation rather than
  retraining the expected-minutes model.
- Chip comparisons optimize within the selected horizon and do not assign an external value to
  saving a chip beyond that horizon.

## License and contributions

Licensed under the MIT License. Issues and pull requests are welcome. Please include tests for
behavior changes and run the verification commands above before contributing.
