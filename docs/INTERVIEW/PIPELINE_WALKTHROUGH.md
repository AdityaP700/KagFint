# Pipeline Walkthrough: every stage, its code, its tests, its failure modes

A stage-by-stage map of the pipeline. For each stage: what it does, the exact
command, the code entry point, the tests that guard it, and the ways it is
designed to fail loudly.

The golden rule across all stages: **each stage consumes only validated,
frozen outputs of the previous stage, and each run leaves a manifest.**

## Stage 0: Data acquisition

- Command: `kaggle competitions download -c rohlik-sales-forecasting-challenge-v2 -p data/raw`
- Code: none (Kaggle CLI); credentials in `~/.kaggle` or `.env`.
- Outputs: 47.3 MB zip + 299 MB CSVs in `data/raw/`, treated as immutable.
- Failure modes: 403 (rules not accepted), partial downloads. Both surface as
  CLI errors; `dataset.py` raises `FileNotFoundError` with instructions if
  downstream stages are run on an empty raw directory.

## Stage 1: Ingestion + validation gate

- Command: `PYTHONPATH=src python -m demandops.pipeline`
- Code: `src/demandops/dataset.py` (typed table registry and loaders),
  `validation.py` (check battery), `pipeline.py` (orchestration).
- Tests: `tests/test_validation.py` (16) — missing column, wrong dtype,
  duplicate business keys, missing dates, negative sales, null-heavy columns,
  referential breaks, empty-contract violations.
- Failure modes and design:
  - Schema drift -> FAIL, exit code 1. Downstream stages must not run.
  - Anomalies (null targets, date gaps, corrupt discounts) -> WARN with
    quantified evidence in the JSON report; rows preserved, never dropped.
  - Every run writes `validation_report_<ts>.json` and a run manifest
    (git SHA, row counts, summary) to `data_quality_reports/`.

## Stage 2: Database load

- Command: `PYTHONPATH=src python -m demandops.db [--force]`
- Code: `db.py` — applies `sql/ddl/001_schema.sql`, seeds warehouses, loads
  via psycopg3 COPY with explicit column lists.
- Tests: `tests/test_db.py` (4, integration, skipped without DATABASE_URL) —
  row counts equal CSV counts, date bounds, zero orphans, value ranges.
- Failure modes: missing DATABASE_URL raises with instructions (the DB layer
  never guesses credentials); row-count mismatch raises after load; in-database
  referential check (0 orphan sales rows) raises if violated. Idempotent:
  matching counts skip; `--force` truncates and reloads.

## Stage 3: SQL analytics

- Command: `PYTHONPATH=src python -m demandops.sql_runner`
- Code: 18 queries in `sql/analytics/*.sql`, one business question each
  (catalog: `docs/SQL_CATALOG.md`), executed sequentially on one connection.
- Outputs: CSVs in `data/processed/analytics/` + run manifest.
- Failure modes: any query error is captured per query, reported in the
  manifest, and fails the batch (exit 1). The data-grain traps (order-count
  intra-day variance; corrupt discounts excluded explicitly in query 08) are
  documented inside the SQL files themselves.

## Stage 4: Forecasting

### Baselines
- Command: `PYTHONPATH=src python -m demandops.evaluate`
- Code: `baselines.py` (seasonal naive lag-7, moving average 28d),
  `metrics.py` (WMAPE unweighted/weighted, MAE, RMSE), `evaluate.py`.
- Tests: `tests/test_forecasting.py` (13) — metric math, pattern tiling,
  flatness, gap repair regression, cold-start fallback, null propagation.
- Failure modes: series are regularized to a gapless daily grid (forward-fill,
  documented); cold-start and zero-history series use documented fallbacks
  reported in `attrs`; the evaluator raises if any holdout row lacks a
  prediction (it has caught three real bugs, see `docs/INTERVIEW/FAILURES.md`).

### Gradient boosting
- Command: `PYTHONPATH=src python -m demandops.train_gbm`
- Code: `features.py` (leak-safe builder + temporal split),
  `train_gbm.py` (XGBoost hist/cuda, inner-validation early stopping, final
  fit on all pre-holdout data, seeded 42).
- Tests: `tests/test_features.py` (5) — lag/rolling correctness, the
  leakage-spike test, cold-start retention, split sizes.
- Failure modes: NaN features retained (XGBoost native handling) so cold-start
  rows are covered; label-null rows dropped from training only; holdout
  predictions persisted to `data/processed/forecasts/` so later layers never
  retrain. Leakage policy is documented in the module docstring and enforced
  by construction (shifts >= 28 days).

## Stage 5: Stockout risk

- Command: `PYTHONPATH=src python -m demandops.risk`
- Code: `risk.py` — recent availability (OBSERVED), forecast units (DERIVED),
  assumed future availability and tier thresholds (ASSUMED).
- Tests: `tests/test_risk.py` (7) — tier boundaries, zero demand/availability,
  missing-history data gaps, determinism.
- Failure modes: missing input file raises with the corrective command;
  series without availability history are flagged and assumed fully available
  (a data gap is a data-fix action, not fabricated scarcity).

## Stage 6: Recommendations

- Command: `PYTHONPATH=src python -m demandops.recommendations`
- Code: `recommendations.py` — input contract validation, versioned rules
  (R0-R4), quantity formula with invariants, priority ordering.
- Tests: `tests/test_recommendations.py` (30) — contract failures, quantity
  invariants across magnitudes, pack multiples, action mapping, degradation
  paths (unknown tier, NaN availability, data gaps), rationale truthfulness,
  determinism, output shape.
- Failure modes: contract violation raises listing every missing column;
  unknown tiers degrade to monitor; data gaps degrade to investigate_data;
  zero-unmet rows recommend zero units. Every input row yields exactly one
  valid action.

## Stage 7: What-if simulator

- Command: `PYTHONPATH=src python -m demandops.simulator --demand-multiplier 1.2 ...`
- Code: `simulator.py` — pure `apply_scenario()`, CLI wrapper, consistency
  gate (identity scenario must reproduce the risk table), scenario CSV +
  summary JSON + manifest.
- Tests: `tests/test_simulator.py` (13) — lever math, caps, baseline-column
  immutability, invalid-parameter refusal, formula equality with the
  recommendation engine, determinism.
- Failure modes: invalid parameters raise; baseline mutation is impossible by
  construction (copy + new columns) and checked; history is never written to.

## Stage 8: Presentation

- Commands: `report` (terminal), `dashboard` (static HTML), `api` (uvicorn).
- Code: `report.py` (rich), `dashboard.py` (self-contained HTML), `api.py`
  (FastAPI, OpenAPI at /docs), `bi_load.py` (curated `bi` schema for BI tools).
- Tests: `tests/test_api.py` (15 — health, 404/422/503 contracts, filters,
  simulation, OpenAPI), `tests/test_dashboard.py` (2 — content, no external
  assets).
- Failure modes: missing artifacts -> 503 with the corrective command; unknown
  series -> 404; malformed params -> 422; NaN-safe JSON serialization;
  request paths never train models or touch the database.

## Stage 9: CI and deployment

- `.github/workflows/tests.yml`: pytest on every push (DB tests self-skip).
- `.github/workflows/pages.yml`: deploys the dashboard to GitHub Pages.
- `render.yaml`: Render free-tier blueprint for the API (build + start +
  health check preconfigured).
- Neon: the curated `bi` schema (three tables, ~3.7k rows each) loaded from
  the same artifacts; connection string lives only in `.env` / secrets.
