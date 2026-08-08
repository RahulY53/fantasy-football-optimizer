# FPL Optimizer

An open-source, local-first Fantasy Premier League forecasting and decision engine.

Phase 1 provides resilient official FPL ingestion, a local SQLite database, cached/offline
operation, and player and fixture browsers. Phase 2 adds expected minutes and explainable
statistical xPts across the next six Gameweeks. Phase 3 adds optional bookmaker-odds imports,
fair market probabilities, Poisson implied goals, independent market xPts, and an adjustable
statistical/market blend. Phase 4 adds user strategy profiles, normalized player optimization
scores, presets, and exact score contribution breakdowns. Phase 5 turns those utilities into the
best legal 15-player initial squad under FPL budget, position, and club constraints. Further
team-management phases are described in [DESIGN.md](DESIGN.md). Phase 6 adds current-squad state
and a next-Gameweek lineup, captaincy, and bench decision engine. Phase 7 compares rolling a free
transfer with the best legal one- and two-transfer plans, including selling prices, bank, and hits.
Phase 8 jointly optimizes a two-to-six-Gameweek path of transfers, legal starting XIs, captains,
free-transfer carry, hits, and bank balances.
Phase 9 adds BTTS and team-total markets, player-linked goalscorer odds, richer official FPL
performance signals, and an improved expected-minutes model.
Phase 10 adds reproducible current-team Monte Carlo simulation with weekly and horizon outcome
distributions, correlated club-level shocks, and player blank, return, and haul probabilities.
Phase 11 evaluates Wildcard, Free Hit, Bench Boost, and Triple Captain opportunities and presents
consistent one-decimal decision outputs throughout the frontend.
Phase 12 imports final historical player/Gameweek outcomes, excludes any forecast created or
sourced after its deadline, and calibrates statistical/market blend weights with chronological
holdout evaluation when enough Gameweeks are available.
The live-data increment adds public Team ID squad import and an optional cached Odds-API.io EPL
connector while preserving the existing forecast → preference → optimization boundaries.
The 2026/27 scoring upgrade adds defensive contributions, current goalkeeper goal scoring,
threshold-based save points, and explicit cards, penalties, own goals, and conceded-goal bands.

## Local setup

Python 3.12 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
streamlit run frontend/streamlit_app.py
```

The first refresh downloads `bootstrap-static` and fixtures from the public FPL service.
Later launches can use the local cache and database when the service is unavailable.
After refreshing, select **Generate advanced forecasts** in the sidebar to create the current
six-Gameweek projection. The model and its limitations are documented in
[docs/model_card.md](docs/model_card.md).

### Phase 3 market workflow

Open **Markets** in the app, then either enter one fixture's decimal odds manually or upload the
long-form CSV template available on that page. Each fixture needs a complete 1X2 market (home,
draw, away) and over/under 2.5 market. Multiple bookmakers are supported and are combined into a
consensus after their margin is removed.

Select a de-vig method and choose **Generate market forecasts**. The **Market influence** slider
then controls the display blend throughout Players and Forecasts: 0 is statistical-only, 100 is
market-only where market coverage exists, and the default is 30. Fixtures without odds safely
fall back to the statistical forecast. The full methodology and limitations are in
[docs/market_model_card.md](docs/market_model_card.md).

### Phase 4 strategy workflow

Open **Strategy** and choose Simple or Advanced mode. Start from Balanced, Conservative,
Aggressive, Value Hunter, Differential, Short-Term Attack, or Long-Term Planner, then adjust the
planning horizon and feature weights. Raw slider values do not need to total 100; the app shows
their normalized weights and updates every player's score dynamically.

The strategy page also shows a plain-language profile summary and a contribution breakdown whose
rows sum exactly to each player's optimization score. The active strategy carries into the Players
table for the current browser session. Named custom strategies can be saved locally. Forecast
settings remain separate: changing a strategy never changes statistical, market, or blended xPts.
See [docs/strategy_model_card.md](docs/strategy_model_card.md) for formulas and limitations.

### Phase 5 initial squad workflow

Open **Optimizer** after generating forecasts and choosing a strategy. Set the available budget,
optionally lock must-buy players or exclude unwanted players, and select **Optimize 15-player
squad**. The binary integer program returns exactly 2 goalkeepers, 5 defenders, 5 midfielders, and
3 forwards, with no more than three players per club and no overspend.

The result separates total strategy objective from projected xPts, shows a constraint audit, and
stores the run inputs and selected squad locally for reproducibility. Starting XI and captaincy
decisions are handled separately on My Team. See [docs/optimizer_model_card.md](docs/optimizer_model_card.md).

### Phase 6 current team workflow

Open **My Team** and either select 15 players manually or choose **Use latest optimized squad** to
import the newest Phase 5 result. Review purchase and selling prices, bank, free transfers, and chip
availability, then save the team. Select **Optimize lineup** to evaluate every legal FPL formation
and return the highest-next-Gameweek-xPts XI.

The screen displays the lineup on a pitch with captain and vice-captain markers, an ordered
three-player outfield bench plus backup goalkeeper, and separate expected, safe, ceiling, and
differential captaincy views. The methodology is documented in
[docs/lineup_model_card.md](docs/lineup_model_card.md).

### Phase 7 transfer workflow

After saving a current squad, open **Transfers**. Choose a one-to-six-Gameweek horizon and how
reluctant you are to spend a transfer, then select **Evaluate roll and transfers**. The optimizer
solves the best legal final squad using exactly zero, one, and two transfers. It uses your saved
selling prices and bank, preserves squad and club constraints, and subtracts four projected points
for each transfer beyond the saved free-transfer allowance.

The screen compares gross gain, hit cost, net gain, ending bank, and full-squad horizon xPts. A
non-zero plan is recommended only when its net gain exceeds the value assigned to preserving
transfer flexibility. The strategy score only breaks near-identical xPts ties; it does not rewrite
the forecast. See [docs/transfer_model_card.md](docs/transfer_model_card.md) for the exact objective,
threshold, and limitations.

### Phase 8 multi-Gameweek planning workflow

Open **Planner** after saving a current squad and generating forecasts. Choose a horizon from two
to six Gameweeks, then select **Build multi-Gameweek plan**. Unlike running the transfer optimizer
repeatedly, this solves every week together: a future fixture swing can justify rolling now,
delaying a purchase, or taking a hit. Each planned week contains transfers, free transfers before
and after, bank, formation, starting XI, captain, gross xPts, and hit-adjusted net xPts.

Free transfers carry up to five and every transfer beyond the available allowance costs four
points. Every intermediate squad and lineup remains legal. Current prices are held static and the
search retains all current players plus the strongest 35 alternatives per position for predictable
desktop solve times. See [docs/planner_model_card.md](docs/planner_model_card.md).

### Phase 9 advanced forecasting workflow

Generate forecasts from the sidebar to use the Phase 9 expected-minutes and statistical model. It
combines starts and minutes share for role estimation, learns substitution involvement from
residual minutes, and uses bounded ICT, form, and BPS adjustments alongside the existing shrunk
goal, assist, save, and bonus rates. Forecast explanations show the multipliers applied.

On **Markets**, the required baseline remains 1X2 and match total 2.5. BTTS, home team total 1.5,
and away team total 1.5 can be entered manually or by CSV and are included in the same implied-goal
fit when complete. CSV also accepts `anytime_goalscorer` rows with the official FPL `player_id`;
these refine how team xG is allocated to players. Missing advanced markets fall back safely to the
baseline. See [docs/advanced_forecasting_model_card.md](docs/advanced_forecasting_model_card.md).

### Phase 10 simulation workflow

Save a current team and generate forecasts, then open **Simulation**. Choose a one-to-six-Gameweek
horizon, 1,000–50,000 iterations, and a random seed. The model selects the highest-expected legal
XI and captain for each week before simulating appearance, goals, assists, clean sheets, saves,
bonus, and deductions.

Results include the mean, median, standard deviation, P10/P90 range, a total-points histogram,
weekly ranges, and each selected player's horizon blank, return, and haul probabilities. Same-club
players share attacking and clean-sheet shocks, so correlated stacks retain their real upside and
downside. Runs are saved and the same seed reproduces the same draws. See
[docs/simulation_model_card.md](docs/simulation_model_card.md).

### Phase 11 chip workflow

Mark currently available chips on **My Team**, generate forecasts, then open **Chips**. Choose a
one-to-six-Gameweek evaluation horizon and select **Evaluate chip opportunities**. Wildcard builds
the best permanent squad for the full horizon; Free Hit searches every Gameweek for the best
temporary squad; Bench Boost finds the strongest current bench; and Triple Captain finds the best
captain opportunity.

Wildcard and Free Hit use the current squad's saved selling value plus bank, and every generated
squad and XI satisfies FPL budget, position, and club rules. The four gains are displayed together,
but only one chip can be active in a Gameweek and the Wildcard figure spans the whole horizon while
the other gains affect one Gameweek. See [docs/chip_model_card.md](docs/chip_model_card.md).

### Phase 12 backtesting workflow

Open **Backtesting**, download the CSV template, and add final outcomes using official FPL player
IDs and Gameweek numbers. Import the completed file, then select **Run backtest**. The evaluator
matches each outcome to the latest forecast whose prediction time and input cutoff were both no
later than the Gameweek deadline.

With at least four Gameweeks, earlier weeks select a market blend weight and later weeks report
untouched chronological holdout accuracy. Results include MAE, RMSE, bias, correlation, position
errors, calibration bands, and expected-minutes accuracy where minutes were supplied. Suggested
weights are advisory and never modify the live Market influence setting. See
[docs/backtesting_model_card.md](docs/backtesting_model_card.md).

### Live team and odds workflow

On **My Team**, enter an FPL Team ID and import or refresh the latest publicly published Gameweek
squad. The app displays manager and team metadata, published XI, bench, captain, vice captain,
value, bank, and refresh status, then makes those 15 official player IDs available to every
existing optimizer. Public imports are deliberately labeled **Published GW Squad** because
unpublished transfers, free transfers, and chip state may not be visible.

For live markets, add `FPL_OPTIMIZER_ODDS_API_KEY` to `.env`, restart the app, and open
**Settings · Data Sources**. Normal refreshes use the local cache; manual refresh is explicit.
Events are restricted to the EPL and matched on both teams plus kickoff with a minimum-confidence
gate. Provider failure falls back to cached, manual, CSV, then statistical-only operation. See
[docs/live_data_model_card.md](docs/live_data_model_card.md).

Docker is also supported:

```bash
docker compose up --build
```

The app is then available at `http://localhost:8501`. Add `--profile api` to also run the
optional local API on port 8000.

## Commands

```bash
pytest
ruff check .
mypy fpl_optimizer
uvicorn api.main:app --reload
```

Useful local API endpoints include `GET /forecasts/statistical?market_weight=0.3`,
`GET /forecasts/advanced?market_weight=0.3`, `POST /forecasts/advanced/run`,
`POST /markets/run?devig_method=multiplicative`, `GET /markets`, `GET /strategy/presets`,
`POST /strategy/score`, `GET/POST /strategies`, `POST /optimizer/squad`, and
`GET /optimizer/runs`. Current-team endpoints are `GET/PUT /team/current`,
`POST /team/current/lineup`, and `GET /team/current/lineup-runs`. Transfer endpoints are
`POST /transfers/evaluate` and `GET /transfers/runs`. Planner endpoints are `POST /planner/run`
and `GET /planner/runs`.
Simulation endpoints are `POST /simulation/run` and `GET /simulation/runs`.
Chip endpoints are `POST /chips/evaluate` and `GET /chips/runs`.
Backtesting endpoints are `POST /backtesting/outcomes/import`,
`GET /backtesting/outcomes/count`, `POST /backtesting/run`, and `GET /backtesting/runs`.
Live endpoints are `POST /team/import`, `GET /team/imported`, `GET /odds/live/status`,
`POST /odds/live/test`, and `POST /odds/live/refresh`.

## Data and licensing

The software is MIT licensed. The official FPL API is undocumented and its data should not
be assumed redistributable. Runtime cache and database files are ignored by version control.
See [DESIGN.md](DESIGN.md) for architecture, modelling assumptions, and roadmap.
