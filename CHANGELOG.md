# Changelog

## 2026-09-27

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
