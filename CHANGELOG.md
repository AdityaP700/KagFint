# Changelog

## 2026-09-28

### Checkpoint 06 — Gradient-boosted forecasting on GPU
- Model choice justified and recorded: LightGBM 4.7.0 Windows wheel has no GPU
  support (verified empirically); XGBoost 3.2.0 wheel includes CUDA and runs on
  the RTX 4050 Laptop. Plan permits "LightGBM or another justified GBM".
- Added `features.py`: leak-safe features by construction — weekly lags 28/35/42/56
  and rolling means shifted 28d (every horizon feature predates the cutoff);
  price/discounts treated as known (retailer-set, provided by the competition);
  `total_orders` and `availability` EXCLUDED as leakage (documented).
  NaN features retained for cold-start series (XGBoost native handling).
- Added `train_gbm.py`: two-phase protocol — early stopping on an INNER
  validation window (the 28 days before the holdout), then final fit on all
  pre-holdout data; holdout touched once. GPU-accelerated (hist/cuda),
  ~30s per fit on 3.9M rows.
- **Holdout results (experiments/gbm_results.json):**
  WMAPE 25.21%, weighted WMAPE 31.78%, MAE 29.51, RMSE 95.73.
  vs moving_average_28 (WMAPE 31.64% / 41.30%): −6.4 WMAPE points
  (~20% relative improvement). GBM beats both baselines on all four metrics;
  result and per-warehouse breakdown recorded, not cherry-picked.
- 5 feature tests including a leakage-spike test (a holdout-confined demand
  spike must not appear in any holdout feature). 37/37 tests pass.

### Checkpoint 05 — Baseline forecasting + evaluation harness
- Added `metrics.py` (WMAPE incl. competition-weighted variant, MAE, RMSE),
  `baselines.py` (seasonal naive lag-7, moving average 28d) and
  `evaluate.py` (temporal-split runner).
- Split: final 28 days of history (2024-05-06 → 2024-06-02), matching the
  competition horizon; models see only pre-horizon data.
- **Results (experiments/baseline_results.json):**
  seasonal_naive_7 — WMAPE 33.74%, weighted WMAPE 47.34%, MAE 39.49, RMSE 124.43;
  moving_average_28 — WMAPE 31.64%, weighted WMAPE 41.30%, MAE 37.03, RMSE 118.26.
  Moving average currently beats seasonal naive; preserved as the bar for
  LightGBM.
- Documented fallbacks, all quantified in results: series regularized to a
  gapless daily grid (warehouse date gaps); cold-start series (<7d history,
  6 series/76 rows) use their own available-days mean; zero-history series
  (10 in seasonal naive; 1,613 series without recent rows for the 28d window,
  mostly discontinued) use the global history mean. Hard gate: evaluation
  refuses to run if any holdout row lacks a prediction.
- 12 new tests (metrics edge cases, baseline behavior, gap/cold-start
  regressions). 32/32 pass.
- Added `docs/PROJECT_STORY.md`: layman's narrative of architecture,
  intention, goals, built vs pending.

### 2026-09-27

### Checkpoint 04 — SQL analytics layer
- Added 18 analytics queries (`sql/analytics/`), one business question each,
  cataloged in `docs/SQL_CATALOG.md` with data-grain notes.
- Added `src/demandops/sql_runner.py`: executes all queries sequentially,
  saves CSVs to `data/processed/analytics/`, writes a run manifest.
- Verified all 18 run against the loaded DB; key findings: Friday/Saturday
  demand peaks (~+22% vs Monday); promotions lift avg sales ~36%; units per
  order ~7.7–9.4 by warehouse; Frankfurt_1 (855 days) and Munich_1 (1102 days)
  have the shortest histories.
- Data-grain finding: `total_orders` varies slightly within warehouse-days —
  order queries aggregate its per-warehouse-day mean (documented, explicit in SQL).

### Checkpoint 03 — PostgreSQL schema + loading
- Applied `sql/ddl/001_schema.sql`: dedicated `rohlik` schema, tables
  (`warehouses`, `inventory`, `calendar`, `sales_train`, `sales_test`,
  `test_weights`) with PKs, FKs to `warehouses`, and date/warehouse indexes.
- Created database `kagfint` (PostgreSQL 18, local port 5433).
- Loaded all tables via psycopg3 COPY — row counts verified against CSVs
  (sales_train 4,007,419) plus an in-DB referential check (0 orphan sales rows).
  Loads are idempotent (skip if counts match; `--force` truncates+reloads).
- Added `src/demandops/db.py` (credentials only from `.env`; never logged),
  4 DB integration tests (skip cleanly when no DB configured). 20/20 tests pass.
- Sanity aggregates confirm sane data (e.g. Prague_1 largest, Frankfurt_1
  shortest history).

### Checkpoint 02 — Dataset acquired; ingestion + validation layer
- Downloaded Rohlik Sales Forecasting v2 (47.3 MB zip + 299 MB extracted) to
  `data/raw/` (kept immutable, zip retained for provenance).
- Profiled actual schemas: 4,007,419 train rows, 7 warehouses, 2020-08-01 →
  2024-06-02; `availability` column confirmed as an observed stockout signal.
- Added `src/demandops/dataset.py` (explicit table registry + typed loaders),
  `validation.py` (schema / missingness / duplicates / date-continuity /
  numeric-sanity / referential / coverage checks with PASS-WARN-FAIL statuses),
  `manifest.py` (run manifests with git SHA + file provenance),
  `pipeline.py` (orchestrator, writes validation report + manifest, exits
  nonzero on FAIL).
- First full run: overall WARN — 52 null sales rows; Frankfurt_1 missing 53
  days / Munich_1 missing 8 days; 32 rows (0.0008%) with corrupt discount
  fractions (min -20.9); 42 metadata-only inventory ids. All quantified and
  preserved, none silently dropped. See `docs/DATASET.md`.
- 16 tests pass (`tests/test_validation.py`): clean data passes, each defect
  class (missing column, wrong dtype, duplicates, missing dates, negative
  sales, null-heavy columns, referential breaks, material corruption) yields
  an explicit FAIL/WARN with evidence.

### Checkpoint 01 — Initial project structure
- Initialized repository layout: `src/demandops/`, `sql/`, `tests/`, `docs/`,
  `experiments/`, `data_quality_reports/`, `data/{raw,interim,processed,external}/`.
- Added central configuration module (`src/demandops/config.py`) with
  repo-root-relative paths and `.env` loading.
- Added `.gitignore` (protects raw data, secrets, venv, caches, large artifacts),
  `.env.example`, `requirements.txt`, `README.md`, `AGENTS.md`.
- Environment noted: Python 3.11.9, NVIDIA RTX 4050 Laptop (6 GB) available for
  GPU-accelerated training; PostgreSQL 17/18 installed locally (not on PATH).
