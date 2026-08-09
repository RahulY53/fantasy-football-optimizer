# FPL Optimizer

FPL Optimizer

An open-source, local-first Fantasy Premier League (FPL) forecasting, simulation, and decision engine for power users who want reproducible, offline-capable analytics for squad selection, transfers, lineups, captaincy, and chip strategy.

Player data quality now uses official full names throughout detailed tables, saved teams,
forecast selectors, strategy outputs, and backtests. Search accepts first names, surnames, FPL web
names, partial text, and unaccented input; team and position remain available for disambiguation.
The identity and fallback rules are documented in
[docs/player_name_data_quality.md](docs/player_name_data_quality.md).

The player browser now uses a reusable combined filter system and a cached analytics dataset with
one centralized metric registry. Team, position, price, ownership, expected-minutes, forecast,
risk, and strategy-score filters work together without rerunning forecast or optimization models.
See [docs/player_analytics_foundation.md](docs/player_analytics_foundation.md).

The dedicated Player Analytics page adds configurable player exploration, raw comparison tables,
and position-aware Plotly radar charts for two to five players. Radar scores use a selectable
comparison universe and retain raw values in hover details. See
[docs/player_analytics_compare.md](docs/player_analytics_compare.md).

The analytics 2×2 matrix plots any two available raw metrics, supports multiple player populations
and reference methods, and explains each quadrant with ranked candidates. Seven presets cover
value, threat, minutes, ownership, and market/model disagreement. See
[docs/player_matrix.md](docs/player_matrix.md).

Selected players can also be compared across future fixtures with weekly and cumulative blended
xPts curves, separate attacking and defensive fixture difficulty, and local CSV exports. See
[docs/player_forecast_analytics.md](docs/player_forecast_analytics.md).

Explorer rows, matrix selections, My Team, and optimized-squad results can now feed directly into
the same two-to-five-player comparison workspace. See
[docs/player_compare_workflow.md](docs/player_compare_workflow.md).

The local SQLite-backed Player Watchlist tracks current forecast and decision metrics, supports
combined Watchlist filtering and personal notes, and feeds watched players into Compare. See
[docs/player_watchlist.md](docs/player_watchlist.md).

The **Changes** view compares the latest two stored FPL, statistical, and market observations to
surface meaningful xPts, minutes, price, ownership, market, and availability movements—with
Watchlist filtering, Compare handoff, and CSV export. See
[docs/player_change_detection.md](docs/player_change_detection.md).

The **Weekly Decision Dashboard** refreshes or reuses cached evidence, then combines lineup,
transfer, multi-Gameweek planning, simulation, and chip outputs into one recommendation card with
transparent confidence and risk. See
[docs/weekly_decision_dashboard.md](docs/weekly_decision_dashboard.md).

Overview

FPL Optimizer combines statistical forecasting, bookmaker market signals, optimization, and simulation to support decisions across an FPL season.

The application is designed to be:

- Local-first — data is cached in a local SQLite database for fast, resilient, and offline-capable operation.
- Forecast-driven — generates expected points (xPts), expected minutes, and multi-Gameweek projections.
- Market-aware — optionally incorporates bookmaker odds into player forecasts.
- Optimization-based — uses integer programming to construct legal squads, select lineups, evaluate transfers, and plan across multiple Gameweeks.
- Simulation-enabled — uses reproducible Monte Carlo simulation to quantify uncertainty and upside/downside.
- Extensible — forecasting, strategy, optimization, simulation, and backtesting components are modular and documented.

---

Features

FPL Data

The application retrieves official FPL player, team, and fixture data and stores it locally.

Features include:

- Official FPL "bootstrap-static" ingestion
- Fixture ingestion
- Local SQLite caching
- Offline and resilient operation after data has been downloaded
- Refreshable datasets for new Gameweeks

The first data refresh downloads the latest player and fixture information from the public FPL service.

---

Player Forecasting

The forecasting engine estimates player performance across upcoming Gameweeks.

It generates:

- Expected points (xPts)
- Expected minutes
- Multi-Gameweek projections
- Player-level forecast components
- Explainable contribution breakdowns

Forecasts can be generated using statistical models alone or combined with bookmaker market information.

---

Betting Market Integration

Bookmaker odds can be incorporated as an additional forecasting signal.

The market layer supports:

- 1X2 match odds
- Over/Under 2.5 goal markets
- Decimal odds
- CSV market imports
- Manual single-fixture odds entry
- Multiple de-vigging methods
- Implied goal estimation
- Market-derived fixture expectations
- Statistical/market forecast blending

Users can control Market Influence from 0–100%, allowing the forecasting model to range from entirely statistical to heavily market-driven.

An optional live Odds API connector is also available through:

"FPL_OPTIMIZER_ODDS_API_KEY"

The application falls back safely when live odds are unavailable.

See "docs/market_model_card.md" for methodology and assumptions.

---

Strategy & Custom Weighting

Forecasts describe expected player performance. Strategy determines how those forecasts should be valued by the optimizer.

Built-in strategies include approaches such as:

- Balanced
- Conservative
- Aggressive
- Value Hunter
- Differential

Users can also create their own strategy using Simple or Advanced weighting controls.

Strategy scores are normalized before optimization, while the underlying player forecasts remain unchanged.

Custom strategies are stored locally and can be reused.

Player-level contribution breakdowns explain why each player receives their strategy score.

---

Initial Squad Optimizer

The squad optimizer constructs the highest-scoring legal 15-player FPL squad based on the selected forecasts and strategy.

Every generated squad respects FPL constraints including:

- 2 Goalkeepers
- 5 Defenders
- 5 Midfielders
- 3 Forwards
- FPL budget constraint
- Maximum players per club

Optimization outputs include:

- Selected 15-player squad
- Total squad cost
- Expected performance
- Strategy score
- Constraint audit
- Reproducible optimization inputs

---

My Team Import

Existing FPL managers can import their current squad using their public FPL Team ID.

The application can maintain:

- Current 15-player squad
- Selling prices
- Money in the bank
- Available chips
- Team state for subsequent optimization

This allows the optimizer to work from the manager's real team rather than generating a new squad from scratch.

---

Lineup & Captaincy Optimizer

For an existing 15-player squad, the lineup optimizer determines the best starting XI for a Gameweek.

It evaluates:

- Legal FPL formations
- Starting XI
- Bench ordering
- Captain selection
- Expected Gameweek points

The optimizer searches across eligible lineup combinations and selects the highest-value legal configuration.

---

Transfer Optimizer

The transfer engine evaluates whether a manager should:

- Roll a transfer
- Make one transfer
- Make two transfers
- Take a points hit when justified by expected future returns

Transfer plans account for:

- Players sold
- Players purchased
- Selling prices
- Available bank
- Free-transfer allowance
- Expected points gained
- Future Gameweek value

Additional transfers beyond the free allowance are penalized using the standard 4-point hit.

This allows transfer decisions to be evaluated on expected net value rather than simply identifying the player with the highest next-Gameweek projection.

---

Multi-Gameweek Planner

The planner jointly optimizes decisions across a 2–6 Gameweek horizon.

Instead of optimizing each Gameweek independently, it evaluates sequences of decisions across the planning window.

This can help identify situations where:

- Rolling a transfer is preferable
- A lower immediate return produces greater future value
- Fixture swings justify an earlier transfer
- A transfer hit can be recovered over several Gameweeks
- Squad structure affects future flexibility

The planner therefore treats FPL as a sequential decision problem rather than a series of isolated weekly optimizations.

---

Monte Carlo Simulation

Forecasts represent expected outcomes, but actual FPL results are uncertain.

The simulation engine runs reproducible Monte Carlo simulations using between 1,000 and 50,000 iterations.

Simulation outputs include:

- Expected horizon points
- Outcome distributions
- P10/P90 ranges
- Histograms
- Player-level probabilities
- Blank probability
- Return probability
- Haul probability

The model also supports correlated club-level shocks so that player outcomes from the same match or team are not treated as completely independent.

Fixed random seeds allow simulations to be reproduced.

---

Chip Analysis

The optimizer evaluates opportunities to use:

- Wildcard
- Free Hit
- Bench Boost
- Triple Captain

Chip decisions can be evaluated across a 1–6 Gameweek horizon.

The objective is to compare the expected value of using a chip now against alternative opportunities within the planning window.

---

Backtesting & Model Calibration

Historical outcomes can be imported through CSV and evaluated using chronological holdout backtests.

Backtesting includes:

- Historical forecast comparison
- MAE
- RMSE
- Calibration analysis
- Statistical forecast evaluation
- Market forecast evaluation
- Statistical/market blend evaluation
- Suggested blending weights

Chronological testing is used to reduce the risk of future information leaking into historical evaluations.

This framework allows forecasting assumptions and market influence to be tested empirically rather than selected purely by intuition.

---

Typical Workflow

A typical user journey through the application is:

Refresh FPL Data → Generate Forecasts → Add Market Odds → Choose Strategy → Import or Optimize Squad → Optimize Lineup → Evaluate Transfers → Plan Future Gameweeks → Run Simulations → Evaluate Chips

Each component can also be used independently.

For example, a user can generate statistical forecasts without bookmaker data or run the squad optimizer without importing an existing team.

---

Quickstart

Requirements

- Python 3.12+

Create a virtual environment, install dependencies, migrate the database, and start the application:

python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
streamlit run frontend/streamlit_app.py

The Streamlit application will then run locally.

Docker

docker compose up --build

The application will be available at:

"http://localhost:8501"

Add "--profile api" to also start the optional local API on port "8000".

---

First Run

On the first run:

1. Refresh FPL data.
2. The application downloads "bootstrap-static" and fixture information from the public FPL service.
3. Open the application sidebar.
4. Select Generate advanced forecasts.
5. The application generates the current multi-Gameweek player projection.

See "docs/model_card.md" for forecasting methodology, assumptions, and limitations.

---

Developer API

The application exposes an optional local API for programmatic access.

Forecasting

GET  /forecasts/statistical?market_weight=0.3
GET  /forecasts/advanced?market_weight=0.3
POST /forecasts/advanced/run

Markets

POST /markets/run?devig_method=multiplicative
GET  /markets

Strategy

GET  /strategy/presets
POST /strategy/score
GET  /strategies
POST /strategies

Squad Optimization

POST /optimizer/squad
GET  /optimizer/runs

Team & Lineup

GET  /team/current
PUT  /team/current
POST /team/current/lineup
GET  /team/current/lineup-runs

Transfers

POST /transfers/evaluate
GET  /transfers/runs

Multi-Gameweek Planning

POST /planner/run
GET  /planner/runs

Simulation

POST /simulation/run
GET  /simulation/runs

Chips

POST /chips/evaluate
GET  /chips/runs

Backtesting

POST /backtesting/outcomes/import
GET  /backtesting/outcomes/count
POST /backtesting/run
GET  /backtesting/runs

Live Team & Odds

POST /team/import
GET  /team/imported
GET  /odds/live/status
POST /odds/live/test
POST /odds/live/refresh

---

Development Commands

Run tests:

pytest

Run linting:

ruff check .

Run type checking:

mypy fpl_optimizer

Start the local API:

uvicorn api.main:app --reload

---

Architecture & Documentation

Detailed modelling and implementation documentation is available in the repository.

"DESIGN.md"

Contains:

- System architecture
- Modelling assumptions
- Optimization design
- Application architecture
- Technical roadmap
- Major design decisions

"docs/"

Contains model cards and detailed methodology for individual components, including:

- Forecasting model
- Market model
- Strategy model
- Squad optimizer
- Transfer optimizer
- Multi-Gameweek planner
- Simulation engine
- Chip evaluation
- Backtesting

---

Data & Licensing

License: MIT

The official FPL API is undocumented. Users should respect its applicable terms and should not assume that FPL data can be redistributed.

Runtime cache and database files are excluded from version control.

The application itself is designed around open-source components and local execution.

---

Contributing

Issues and pull requests are welcome.

Before opening a pull request, run:

pytest
ruff check .
mypy fpl_optimizer

Tests, type checks, and linting are included in CI.

See "DESIGN.md" and the "docs/" directory for architecture, design rationale, modelling assumptions, and implementation details.
