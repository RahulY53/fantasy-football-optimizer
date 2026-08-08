# FPL Optimizer — Technical Design

Status: design gate for the first usable MVP  
Target runtime: local laptop, Python 3.12, SQLite, Streamlit  
License: MIT

## 1. Scope and architectural boundaries

The product is a local-first Fantasy Premier League forecasting and decision engine. The first usable release will ingest official FPL data and user-supplied betting odds, produce statistical and market forecasts, apply a separately configured user strategy, and optimize a legal 15-player squad.

The codebase enforces three one-way layers:

1. **Forecast** estimates what is likely to happen. It consumes source data and produces versioned player/fixture projections with uncertainty and timestamps.
2. **Strategy** converts forecast-independent player attributes into normalized preference scores. It never changes a player's statistical or market xPts.
3. **Optimization** selects decisions subject to FPL constraints. It consumes forecasts, strategy scores, costs, squad state, and rules.

Dependencies flow inward through typed domain objects and provider protocols:

```text
External data -> ingestion/cache -> canonical database
                                  -> feature builders
                                  -> statistical forecast ----+
Odds providers -> de-vig -> implied-goals -> market forecast --+-> blended forecast
                                                               |
User configuration -> normalized strategy --------------------+-> optimizer -> result/explanation
                                                                                  |
API / Streamlit <----------------------------------------------------------------+
```

The UI may call application services but must not contain formulas, database queries, optimization constraints, or provider-specific parsing.

## 2. MVP boundaries and release sequence

The master brief is a product roadmap, not a single-release specification. Implementation is split into vertical slices:

- **M0 — foundation:** configuration, logging, database, cached official FPL ingestion, player and fixture browsers.
- **M1 — forecast:** expected minutes, fixture-strength features, statistical xPts, forecast persistence.
- **M2 — markets:** CSV/manual odds providers, de-vig, bookmaker consensus, Poisson implied goals, clean sheets, market xPts, blended xPts.
- **M3 — strategy:** presets, percentile normalization, editable weights, contribution explanations.
- **M4 — optimizer:** legal 15-player squad, locks/exclusions/must-buy constraints, deterministic explanations.
- **M5 — team management:** persistent current team, exact lineup/captain decisions, and exact roll/one/two-transfer comparison.
- **M6 — multi-week planning:** joint transfer, free-transfer, bank, legal XI, and captain path.
- **M7 — advanced forecasts:** richer official signals, BTTS, team totals, and scorer markets.
- **M8 — simulation:** component-level Monte Carlo team distributions and correlated club shocks.
- **M9 — chips:** exact Wildcard and Free Hit squads plus Bench Boost and Triple Captain timing.
- **M10 — backtesting:** atomic historical outcome imports, deadline-safe forecast matching,
  chronological blend calibration, accuracy diagnostics, and persisted evaluation runs.
- **M11 and later:** automated history collection and richer probabilistic calibration.

The first usable MVP is M0–M4. M5–M10 are implemented as the Phase 6–12 team-management,
multi-period planning, advanced-forecasting, simulation, chip, and backtesting baseline. Later
features are represented by stable interfaces but are not advertised as complete.

## 3. Project structure

```text
fpl-optimizer/
├── fpl_optimizer/
│   ├── config.py
│   ├── logging.py
│   ├── domain/
│   │   ├── enums.py
│   │   ├── players.py
│   │   ├── fixtures.py
│   │   ├── forecasts.py
│   │   ├── strategies.py
│   │   └── optimization.py
│   ├── data/
│   │   ├── cache.py
│   │   ├── fpl/{client.py,mapper.py,service.py}
│   │   └── odds/providers/{base.py,csv.py,manual.py}
│   ├── database/{base.py,models.py,repositories.py,migrations/}
│   ├── features/
│   │   ├── expected_minutes.py
│   │   ├── fixture_strength.py
│   │   ├── attacking_share.py
│   │   ├── value.py
│   │   └── risk.py
│   ├── forecasting/
│   │   ├── statistical.py
│   │   ├── market.py
│   │   ├── blend.py
│   │   └── service.py
│   ├── odds/{devig.py,consensus.py,poisson.py,implied_goals.py}
│   ├── scoring/{normalization.py,weights.py,presets.py,score.py}
│   ├── optimizer/{squad.py,lineup.py,captain.py,transfers.py,multiweek.py}
│   ├── backtesting/{snapshots.py,forecast.py,metrics.py,leakage.py}
│   ├── simulation/{match.py,squad.py}
│   └── services/{refresh.py,players.py,fixtures.py,optimize.py}
├── api/{main.py,schemas.py,dependencies.py}
├── frontend/{streamlit_app.py,pages/,components/}
├── config/{defaults.yaml,strategies.yaml}
├── data/{cache/,imports/,exports/}
├── tests/{unit/,integration/,fixtures/}
├── docs/{data_dictionary.md,model_card.md,licenses.md}
├── alembic.ini
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── requirements.txt
├── .env.example
├── LICENSE
└── README.md
```

`fpl_optimizer` is the only package allowed to implement business logic. `api` and `frontend` are adapters. Empty advanced modules will not be created until they expose real behavior.

## 4. Official FPL data

### Endpoints

The official API is undocumented and therefore treated as a replaceable, best-effort provider.

| Endpoint | Use | Refresh policy |
|---|---|---|
| `/api/bootstrap-static/` | players, teams, positions, events, prices, availability, aggregate statistics | manual refresh; at most every 15 minutes |
| `/api/fixtures/` | all fixtures, kickoff times, event assignment, difficulty, results | manual refresh; at most every 15 minutes |
| `/api/element-summary/{id}/` | player fixture history and future fixtures | on demand with per-player cache |
| `/api/entry/{team_id}/` | public team metadata | optional current-team import |
| `/api/entry/{team_id}/event/{gw}/picks/` | public historical/current picks after availability | optional; never assumed available pre-deadline |

Private authentication endpoints are outside the MVP. A team can be entered manually even if public team-ID import changes or becomes unavailable.

### Ingestion rules

- HTTP client uses explicit timeouts, retries only transient failures with capped exponential backoff, and identifies the application.
- Every response is written atomically to a content-addressed local cache before mapping.
- Raw response metadata includes provider, endpoint, retrieval time in UTC, payload hash, HTTP validators, and schema version.
- Validation errors preserve the previous good snapshot and surface a visible stale-data warning.
- Provider DTOs never escape the ingestion package; mappers produce canonical domain records.
- Refresh operations are idempotent database upserts within a transaction.

## 5. Betting-data architecture

```python
class OddsProvider(Protocol):
    def get_snapshots(self, query: OddsQuery) -> list[OddsSnapshotInput]: ...
    def health(self) -> ProviderHealth: ...
```

Initial providers:

- `CsvOddsProvider`: imports historical/current decimal odds using a documented template.
- `ManualOddsProvider`: validates one or more bookmakers entered through the UI.
- A football-data CSV adapter may be added once the source format and redistribution terms are verified.

Optional live/paid providers must live in separate extras and map into the same domain type. Core services never import a vendor SDK.

Required MVP markets are three-way match result and over/under 2.5. Each row carries fixture identity, bookmaker, market, selection, decimal odds, observed-at timestamp, imported-at timestamp, and whether it is opening/current/closing. Fixture matching is explicit and reviewable; ambiguous team-name matches are rejected rather than guessed.

Consensus is built after de-vigging each complete bookmaker market independently:

1. reject invalid/incomplete/stale books;
2. derive fair probabilities within each bookmaker and market;
3. aggregate fair probabilities with the median by default;
4. re-normalize mutually exclusive selections;
5. report median absolute deviation and bookmaker count as uncertainty features.

## 6. Database schema

SQLAlchemy 2.x models use integer primary keys, UTC timestamps, uniqueness constraints, and explicit foreign keys. Money is stored in FPL tenths of a million as integer `price_tenths`; probabilities and projections are floating point.

### Core source entities

- `data_snapshot(id, provider, endpoint, retrieved_at, payload_hash, cache_path, schema_version, is_valid)`
- `gameweek(id, fpl_id, name, deadline_at, is_current, is_next, finished, snapshot_id)`
- `team(id, fpl_id, name, short_name, strengths..., snapshot_id)`
- `player(id, fpl_id, team_id, position, web_name, full_name, status, news, chance_next_round, snapshot_id)`
- `player_snapshot(id, player_id, observed_at, price_tenths, ownership_pct, transfers_in, transfers_out, form, points_per_game, minutes, starts, goals, assists, clean_sheets, saves, bonus, bps, ict...)`
- `fixture(id, fpl_id, gameweek_id nullable, home_team_id, away_team_id, kickoff_at, home_difficulty, away_difficulty, status, snapshot_id)`
- `player_gameweek_stat(id, player_id, gameweek_id, fixture_id, observed_at, points, minutes, starts, goals, assists, xg nullable, xa nullable, ...)`

### Market entities

- `odds_snapshot(id, fixture_id, provider, bookmaker, market, selection, decimal_odds, observed_at, imported_at, snapshot_kind, source_ref)`
- `market_forecast(id, fixture_id, prediction_at, input_cutoff_at, method_version, home_win, draw, away_win, over_2_5, home_xg, away_xg, home_cs, away_cs, dispersion, bookmaker_count)`

### Forecast and strategy entities

- `model_version(id, name, semantic_version, feature_schema, parameter_json, training_cutoff_at, code_revision, created_at)`
- `player_forecast(id, player_id, gameweek_id, fixture_id nullable, prediction_at, input_cutoff_at, model_version_id, stat_xpts, market_xpts nullable, blend_weight, blended_xpts, expected_minutes, floor, ceiling, confidence, component_json)`
- `strategy(id, name, mode, preset_key nullable, horizon, market_weight, risk_appetite, transfer_reluctance, ownership_preference, created_at, updated_at)`
- `strategy_weight(id, strategy_id, feature, raw_weight, position nullable)`

### Decision entities

- `user_team(id, name, bank_tenths, free_transfers, captured_at, source_team_id nullable, chip_json)`
- `user_player(id, user_team_id, player_id, purchase_price_tenths, selling_price_tenths, is_captain, is_vice, bench_order nullable)`
- `optimization_run(id, strategy_id, user_team_id nullable, kind, horizon, forecast_cutoff_at, objective_value, solver_status, solver_version, config_json, created_at)`
- `optimization_selection(id, run_id, player_id, decision, gameweek_id nullable, score, explanation_json)`
- `transfer_plan(id, run_id, gameweek_id, player_out_id nullable, player_in_id nullable, hit_cost, bank_after_tenths, free_transfers_after)`

SQLite is configured with foreign keys enabled and WAL mode. Alembic manages migrations. JSON columns hold versioned explanations/parameters, not fields needed for filtering or integrity.

## 7. Expected-minutes model

The MVP uses an explainable heuristic, not a falsely precise learned model. It produces scenario probabilities:

- `p_start`
- `p_sub_appearance`
- `p_no_appearance = 1 - p_start - p_sub_appearance`
- `minutes_if_start`
- `minutes_if_sub`

Then:

```text
expected_minutes = p_start * minutes_if_start
                 + p_sub_appearance * minutes_if_sub
p_60_plus = p_start * P(minutes >= 60 | start)
```

Features available from official data are recent minutes, starts when present, season minutes per team match, status, chance of playing, news, transfers, and fixture congestion. Recent observations use a time-decayed window, with starts weighted more strongly than substitute appearances. Availability caps the appearance probability; it does not multiply minutes a second time.

MVP priors by role/usage tier prevent tiny samples from producing extremes. Outputs are clipped to `[0, 90]`, expose component values, and receive a confidence grade based on sample size, recent role stability, and availability ambiguity.

Limitations: the official feed does not reliably encode tactical role, training reports, manager quotes, or predicted lineups. Congestion can be measured but rotation policy cannot be inferred robustly early in a season. A trained survival/classification model is deferred until timestamped historical inputs exist.

## 8. Statistical xPts

Forecasts are calculated per fixture and summed within a Gameweek, correctly supporting doubles and blanks.

### MVP opportunity estimates

When open xG/xA inputs are absent, shrink observed goal and assist rates per 90 toward position priors. Team attacking opportunity is adjusted by a transparent strength ratio derived from official home/away attack and opponent defence strengths. With richer data, the same interface accepts shrunk xG/90 and xA/90 instead.

```text
player_xg = shrunk_xg90 * expected_minutes / 90 * fixture_attack_multiplier
player_xa = shrunk_xa90 * expected_minutes / 90 * fixture_attack_multiplier
P(goal >= 1) = 1 - exp(-player_xg)
P(team clean sheet) = fixture model probability
```

### Points components

```text
appearance = P(1..59 minutes) + 2 * P(60+ minutes)
goals      = expected_goals * {GK:6, DEF:6, MID:5, FWD:4}
assists    = expected_assists * 3
cleanSheet = P(60+) * P(team CS) * {GK:4, DEF:4, MID:1, FWD:0}
saves      = expected_save_points for GK, otherwise 0
bonus      = conservative empirical expectation by position and attacking/CS events
deductions = expected cards + goals-conceded deductions + small prior penalties
stat_xPts  = sum(components)
```

The first version uses probability-weighted expected scoring, never a binary assumed start. Save and bonus models begin as documented baselines and are labeled low confidence. Every stored forecast includes all components.

## 9. De-vigging

For decimal odds `o_i`, raw implied probabilities are `q_i = 1/o_i`.

### Multiplicative method (MVP default)

```text
p_i = q_i / sum(q)
```

It is deterministic, works for all complete markets, and is easy to audit.

### Power method

Solve `sum(q_i^k) = 1`, then `p_i = q_i^k`. This changes the favorite/long-shot relationship and requires a bounded scalar root solve.

### Shin method

Estimate the insider-trading parameter using a standard iterative formulation, falling back to multiplicative normalization if convergence or admissibility checks fail.

Each method must return probabilities summing to one within tolerance, the original overround, method name, and diagnostics. Selecting a default beyond multiplicative requires time-ordered calibration tests using Brier score/log loss.

Two-way total-goals markets are de-vigged separately from 1X2. Consensus is never calculated from raw odds across bookmakers.

## 10. Market-implied goals

Assume independent Poisson goals for the first model:

```text
H ~ Poisson(lambda_home)
A ~ Poisson(lambda_away)
```

For a sufficiently large goal grid (adaptive until omitted tail mass is below tolerance), compute model probabilities for home win, draw, away win, over 2.5, and later BTTS.

Estimate positive lambdas by minimizing in log space:

```text
min over theta_h, theta_a:
    Σ_m w_m * (P_model(m; exp(theta_h), exp(theta_a)) - P_market(m))²
    + regularization
```

Bounds correspond to plausible team goal means (initially 0.05–5.0). 1X2 selections are included as a probability vector; over/under contributes one independent target to avoid double counting complements. Market weights may be inversely related to dispersion only after testing; MVP uses explicit equal market-family weights. Multiple initial points reduce local-solver risk.

Derived outputs:

```text
total_xg = lambda_home + lambda_away
home_cs  = exp(-lambda_away)
away_cs  = exp(-lambda_home)
```

Fit residuals, input markets, bounds, grid tail mass, and optimizer success are persisted. A poor fit lowers confidence rather than silently producing authoritative values.

Limitations: independent Poisson understates some score dependence and may misrepresent low-score draws. Dixon–Coles and bivariate variants are candidates only if out-of-sample calibration improves.

## 11. Market xPts

Market team xG is allocated to players using a shrunk share of team attacking output:

```text
attacking_share_i = shrink(player attacking contribution / team contribution,
                           position-and-role prior)
player_market_xg  = team_market_xg * goal_share_i * availability_adjustment
player_market_xa  = team_market_xg * assist_share_i * availability_adjustment
```

Shares are defined on a 90-minute/available-player basis and re-normalized among plausible participants to prevent double-applying expected minutes. Penalty and set-piece roles can add explicit, bounded adjustments when data exists.

Appearance, goals, assists, clean sheets, saves, bonus, and deductions use the same scoring component functions as statistical xPts. Only the event probabilities/opportunities differ. This prevents formula drift between the two forecasts.

Without player xG/xA data, goal/assist shares use shrunk FPL goal involvement and position priors and are marked low confidence. Match odds alone cannot reliably identify which individual will score.

## 12. Statistical/market blend

For market influence `m in [0, 1]`:

```text
blended_xPts = (1 - m) * statistical_xPts + m * market_xPts
```

This setting belongs to forecast configuration and is visually separated from strategy. If no valid market forecast exists, the application uses statistical xPts, shows the fallback, and does not pretend that the requested weight was applied.

The MVP default is a conservative documented placeholder (initially 0.30), not a claim of optimality. Historical rolling-origin backtests select future defaults globally, then optionally by position and horizon. Candidate weights are evaluated from 0.0 to 1.0 in 0.1 increments, with a locked final test period and confidence intervals. Complexity is retained only if it improves forecast and decision metrics out of sample.

`market_edge = market_xPts - statistical_xPts` is shown as diagnostic disagreement, never automatically added again to optimization score.

## 13. Feature normalization and user weights

Features are normalized within relevant comparison groups, normally position and forecast horizon, using percentile ranks on the current eligible player pool:

```text
positive feature score = percentile(feature) * 100
risk penalty score      = percentile(risk) * 100
```

Ties use average rank. Missing values receive a documented neutral or conservative value by feature; they are never silently converted to zero. Small groups fall back to robust min-max scaling or league-wide percentiles. Normalization context and timestamp are stored so an explanation can be reproduced.

Raw user weights need not sum to 100:

```text
normalized_weight_j = raw_weight_j / Σ abs(raw_weight)
optimization_score  = Σ normalized_weight_j * direction_j * normalized_feature_j
```

The displayed 0–100 score is an affine presentation of the signed result; the optimizer uses the unrounded underlying objective. Ownership preference is signed from -100 (differential) through 0 to +100 (template). Risk appetite controls the penalty attached to variance/uncertainty but never changes xPts. Position-specific weights inherit global values unless explicitly overridden.

Every result includes per-feature contribution, raw value, percentile, raw weight, normalized weight, and direction. Presets are YAML data with version identifiers. Saving an edited preset creates a new strategy rather than mutating the shipped preset.

## 14. Squad optimizer

For each eligible player `i`, let binary `x_i` indicate selection. The single-period integer program is:

```text
maximize Σ_i x_i * score_i

subject to
Σ_i x_i = 15
Σ_{i in GK}  x_i = 2
Σ_{i in DEF} x_i = 5
Σ_{i in MID} x_i = 5
Σ_{i in FWD} x_i = 3
Σ_{i in club c} x_i <= 3        for every club c
Σ_i price_i * x_i <= budget
x_i = 1                          for locked/must-buy players
x_i = 0                          for excluded players
x_i in {0,1}
```

OR-Tools CP-SAT is preferred because prices and scores can be safely scaled to integers and later transfer planning benefits from a capable discrete solver. Exact unrounded totals are recalculated after solving. Preflight validation catches contradictory locks, too many players from a club/position, and infeasible budgets. Solver status, bounds, timeout, and deterministic seed/worker settings are recorded.

The objective defaults to strategy score, whose strongest positive feature is blended xPts. The UI also reports projected points separately so a strategy-heavy squad cannot be mistaken for the maximum-xPts squad.

## 15. Multi-Gameweek optimizer concept

This is a separate later milestone and will not be approximated by greedily repeating one-week transfers.

For player `i`, week `t`:

- `s[i,t]`: owned after transfers
- `buy[i,t]`, `sell[i,t]`: transfer decisions
- `start[i,t]`, `captain[i,t]`, `bench_slot[i,t]`: lineup decisions
- state: bank, free transfers, purchase prices/selling values, chips remaining

Core transition:

```text
s[i,t] = s[i,t-1] + buy[i,t] - sell[i,t]
```

Each week enforces squad and lineup rules. Bank changes use forecast price scenarios and actual selling-value rules. Free-transfer state is a small discrete state machine reflecting the season's current official rules, which must be configuration-driven rather than hard-coded. Hits equal chargeable transfers times four points. The objective maximizes discounted expected lineup/captain points plus bounded strategic utility, minus hits and transfer-reluctance costs, plus an explicitly validated terminal flexibility value.

Because purchase-price history and non-linear selling values complicate a pure linear formulation, initial implementation may use CP-SAT with discrete price state or beam search/dynamic programming over feasible squads. The chosen method must compare against small brute-force cases. Alternative plans are produced by no-good constraints or k-best search.

Chip variables are excluded until each chip's state transitions and incremental value pass independent tests.

## 16. Backtesting and calibration

Backtesting uses immutable, timestamped snapshots and rolling-origin evaluation:

1. choose a historical deadline `d`;
2. construct features only from records with `observed_at <= d`;
3. use odds observed no later than `d`;
4. create forecasts with an explicit model version and input cutoff;
5. score against outcomes only after the forecast is frozen;
6. advance to the next deadline without refitting on future weeks.

Forecast metrics: MAE, RMSE, Spearman rank correlation, probability calibration curves, Brier score, and log loss where applicable. Decision metrics: legal optimized squad points, captain points, transfer net gain after hits, regret versus hindsight (clearly labeled), FPL average, and simple baselines such as total-points/form ranking.

Model selection uses training/validation seasons or expanding windows; a final period remains untouched. Statistical, market, and blended models are evaluated on the same eligible-player rows. Bootstrap confidence intervals quantify whether differences are meaningful.

### Leakage controls

- Assert every source observation and odds snapshot is at or before the FPL deadline.
- Never reconstruct old forecasts from today's player status, price, fixture assignment, or cumulative totals.
- Do not use actual lineups, post-deadline team news, closing odds after the deadline, later reschedules, or post-match xG.
- Cumulative statistics must be differenced from the last pre-deadline snapshot, not taken from a later season total.
- Split transformations, priors, normalization thresholds, and blend selection are fitted inside each training fold.
- Maintain synthetic tests with deliberately future-dated rows and require the pipeline to reject them.

Historical FPL snapshots are not fully recoverable from the live official API. Credible backtesting therefore depends on collecting data prospectively or importing a timestamped historical archive with known provenance.

## 17. Streamlit wireframe

Global sidebar:

```text
[Data freshness + Refresh]
Forecast model
  Statistical 70% | Market 30%
Strategy: Balanced
Planning horizon: 3 GW
Navigation
```

Pages for the MVP:

1. **Overview / My Team:** empty-state team entry initially; later pitch, bench, captain, summaries.
2. **Players:** search/filter/sort table; selectable player opens forecast component and strategy-contribution panels; compare 2–5.
3. **Fixtures:** Gameweek filters, blanks/doubles, strength and kickoff data.
4. **Markets:** odds import/manual entry, validation report, fair probabilities, implied xG/CS, fit diagnostics.
5. **Strategy:** forecast settings in a distinct card; preset/mode/horizon/preferences; raw and normalized weights; programmatic plain-language summary.
6. **Optimizer:** budget, locks/exclusions, optimize action, legal squad grouped by position, cost, xPts, strategy score, warnings, explanation.

Later navigation adds Transfers, Simulator, and Backtesting only when functional. The interface must always show data timestamps, forecast version, whether market data was used, and stale/fallback warnings.

## 18. API surface

FastAPI is an optional local service over application services, not a requirement for Streamlit to perform HTTP calls in-process.

Initial endpoints:

- `GET /health`
- `POST /data/fpl/refresh`
- `GET /players`
- `GET /players/{id}/forecasts`
- `GET /fixtures`
- `POST /odds/import`
- `GET /markets/fixtures`
- `POST /forecasts/run`
- `GET/POST /strategies`
- `POST /optimizations/squad`
- `GET /optimizations/{id}`

Pydantic request/response schemas are versioned. Domain objects do not depend on Pydantic or FastAPI.

## 19. Dependencies

Core runtime:

- `pandas`, `numpy`, `scipy`: transformations and numerical optimization
- `scikit-learn`: calibration/metrics and later explainable models
- `ortools`: integer optimization
- `sqlalchemy`, `alembic`: persistence and migrations
- `httpx`: FPL client
- `pydantic`, `pydantic-settings`, `PyYAML`: validation/configuration
- `fastapi`, `uvicorn`: local API
- `streamlit`, `plotly`: UI and charts
- `tenacity`: bounded transient retry policy

Development:

- `pytest`, `pytest-cov`, `hypothesis`, `respx`: tests and HTTP fixtures
- `ruff`, `mypy`: formatting/linting/type checks

Dependencies will be pinned with compatible ranges in `pyproject.toml` and resolved reproducibly. Pandas remains an adapter/analysis tool; domain and optimizer interfaces use typed records to avoid DataFrame-shaped coupling.

## 20. License review

The project will use the MIT license. The planned primary dependencies are generally permissive (BSD/MIT/Apache-2.0), but exact installed versions and transitive license metadata must be captured in `docs/licenses.md` before a release. OR-Tools is Apache-2.0; SciPy/scikit-learn/pandas/NumPy use BSD-style licenses; FastAPI, SQLAlchemy, Streamlit, Plotly.py, Pydantic, HTTPX, PyYAML, pytest, Ruff, and mypy use permissive licenses.

Data licensing is separate from software licensing. The official FPL API is undocumented and its data must not be assumed freely redistributable. Raw cache files and imported odds will be excluded from source distributions. Each optional football-data connector must document source terms, attribution, scraping policy, and redistribution constraints before inclusion. No connector should bypass access controls or site terms.

## 21. Free/local deployment

Primary path:

```text
Browser -> Streamlit process -> application services -> SQLite + local cache
                         \----> optional FastAPI process
```

Local installation supports a virtual environment plus `streamlit run frontend/streamlit_app.py`. Docker uses a non-root user, a mounted `/app/data` volume, health checks, and no required external service. `compose.yaml` runs Streamlit and optionally FastAPI against the same persistent SQLite volume; concurrent writes are serialized and low-volume.

For low/no-cost hosting, deploy the same container to any platform supporting persistent storage, or run Streamlit alone. Ephemeral free tiers lose SQLite/cache state on restart and therefore require export/import or an optional PostgreSQL URL. No platform-specific SDK enters core code. Secrets are only needed for optional providers and are loaded from environment variables.

## 22. Assumptions and modelling shortcuts

### Assumptions

- The public FPL endpoints remain reachable, but failures and schema drift are expected.
- Current official FPL squad/transfer/price rules are configurable and verified each season.
- Odds are decimal, timestamped, and matched to fixtures before use.
- A Gameweek may contain zero, one, or multiple fixtures per player.
- Optimization operates only on players eligible under the selected forecast cutoff.

### MVP shortcuts

- Explainable priors and heuristics replace trained expected-minutes, save, bonus, card, and variance models.
- Independent Poisson is the initial market score model.
- Multiplicative de-vig is the initial default.
- Official strengths and shrunk FPL rates stand in for richer open xG/xA when unavailable.
- Floor/ceiling and confidence are labeled heuristics until simulation/calibration exists.
- The initial optimizer builds a squad; it does not yet claim optimal transfer or chip advice.

### Data limitations

- Live official data does not provide a reliable historical pre-deadline snapshot archive.
- Public xG/xA and odds sources vary in coverage, timestamp quality, terms, and format.
- Player markets are not required, so individual market xPts necessarily allocates team-level information using uncertain shares.
- Injury news and rotation intent are incomplete and often qualitative.
- Selling value requires purchase-price history; current market price alone is insufficient.

### Decisions that require backtesting

- Expected-minutes priors, decay window, and availability treatment
- Fixture-strength multipliers and shrinkage strength
- Statistical opportunity rates and position priors
- De-vig method and bookmaker aggregation
- Implied-goals market-family weights and Poisson alternatives
- Statistical/market blend globally, by position, and by horizon
- Bonus/save/deduction baselines
- Strategy normalization groups and any terminal transfer-flexibility value
- Floor/ceiling estimates and risk score calibration

## 23. Testing strategy

Unit tests cover:

- de-vig probability sums, invalid odds, power/Shin convergence and fallbacks;
- Poisson score-grid mass, win/draw/total/CS probabilities, and known lambda recovery;
- expected-minutes scenario arithmetic and bounds;
- FPL scoring by position and 60-minute probability;
- blend endpoints (`m=0`, `m=1`) and missing-market fallback;
- percentile ties, missing data, signs, and weight normalization;
- optimizer legality, infeasibility, locks/exclusions, and brute-force agreement on small pools;
- blank/double Gameweek aggregation;
- timestamp leakage rejection.

Integration tests use recorded synthetic fixtures, never the live API. A separate opt-in smoke test checks current provider compatibility. Randomized tests use fixed seeds.

## 24. MVP acceptance criteria

The M0–M4 milestone is complete when a fresh clone can:

1. install locally or start with Docker Compose;
2. refresh/cache/map current FPL players, teams, events, and fixtures, with graceful offline fallback;
3. browse/filter players and fixtures with visible timestamps;
4. import validated 1X2 and O/U 2.5 odds from CSV/manual entry;
5. display overround, fair probabilities, consensus, implied home/away xG, clean-sheet probabilities, and fit quality;
6. generate component-level statistical, market, and blended xPts for six Gameweeks, including blanks/doubles;
7. change market influence without changing strategy configuration;
8. apply/save presets and show raw/normalized weights plus score contributions;
9. produce a legal, budget-constrained 15-player squad with locks/exclusions and clear infeasibility errors;
10. pass unit/integration tests and expose model/data versions for every recommendation.

## 25. Immediate implementation plan after design approval

1. Scaffold packaging, configuration, license, quality gates, and database migration setup.
2. Implement canonical domain records, cache, FPL client/mappers, repositories, and refresh service.
3. Add recorded fixtures and unit/integration tests for ingestion.
4. Build the Players and Fixtures Streamlit pages with stale/offline states.
5. Implement expected-minutes and statistical scoring components with model-version persistence.
6. Implement odds provider protocols, CSV/manual import, de-vig, consensus, and implied goals with mathematical tests.
7. Add market/blended forecasts and visibly separated forecast controls.
8. Add strategy normalization, presets, contribution explanations, and strategy UI.
9. Add CP-SAT squad optimization, tests, and the optimizer UI.
10. Package Docker/Compose, document operation/data limitations, and run the full acceptance suite.
