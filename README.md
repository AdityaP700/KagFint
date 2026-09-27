# DemandOps (repo: KagFint)

Quick-Commerce Demand & Inventory Decision Platform — a production-quality
portfolio project covering data validation, SQL analytics, time-series
forecasting, stockout risk, recommendations, a what-if simulator, an API, and
a dashboard.

**Status: Checkpoint 11 — presentation layer.** Full pipeline operational:
validated data → PostgreSQL → SQL analytics → GPU forecasting (XGBoost,
WMAPE 25.2% vs 31.6% baseline) → labeled risk engine → versioned
recommendations → what-if simulator → **presentation**: `rich` terminal
report (`python -m demandops.report`), static decision dashboard
(`python -m demandops.dashboard`, also at API `/dashboard`), and FastAPI
Swagger at `/docs`. Evidence.dev BI path scaffolded in `dashboard/` (status
in `dashboard/README.md`). Evidence: `experiments/`, `data/processed/`.
Plain-language tour: `docs/PROJECT_STORY.md`.

## Current state

- `src/demandops/` — Python package with central path/environment config.
- `sql/`, `tests/`, `docs/`, `experiments/`, `data_quality_reports/` — layer directories (empty, filled per milestone).
- `data/raw|interim|processed|external/` — local data layout (git-ignored; raw data is immutable).
- Isolated environment in `.venv/`; dependencies in `requirements.txt`.

## Planned dataset

Rohlik Sales Forecasting (Kaggle). Schema, row counts, date ranges, and
inventory-signal availability must be verified from the actual downloaded
files before any layer is built on assumptions.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env                            # then fill values locally
```
