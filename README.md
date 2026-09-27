# DemandOps (repo: KagFint)

Quick-Commerce Demand & Inventory Decision Platform — a production-quality
portfolio project covering data validation, SQL analytics, time-series
forecasting, stockout risk, recommendations, a what-if simulator, an API, and
a dashboard.

**Status: Checkpoint 05 — baselines measured.** Data loaded in the `rohlik`
schema (row counts verified), 18 business-question queries running against it
(`docs/SQL_CATALOG.md`), and baseline forecasts evaluated on a strict temporal
split: moving_average_28 WMAPE 31.6% vs seasonal_naive_7 33.7%
(`experiments/baseline_results.json`). For a plain-language tour of the
project, read `docs/PROJECT_STORY.md`.

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
