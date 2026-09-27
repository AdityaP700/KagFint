# DemandOps (repo: KagFint)

Quick-Commerce Demand & Inventory Decision Platform — a production-quality
portfolio project covering data validation, SQL analytics, time-series
forecasting, stockout risk, recommendations, a what-if simulator, an API, and
a dashboard.

**Status: Checkpoint 08 — recommendation engine.** Data loaded in the
`rohlik` schema, 18 SQL analyses, temporal-split evaluation with baselines
(moving_average_28 WMAPE 31.6%) and XGBoost (CUDA) forecasting at
**WMAPE 25.2%**, a labeled-assumption stockout risk engine, and a versioned
deterministic recommendation layer (1,051 replenish-now / 729 scheduled /
1,822 monitor / 137 data investigations). Evidence: `experiments/`,
`data/processed/`. Plain-language tour: `docs/PROJECT_STORY.md`.

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
