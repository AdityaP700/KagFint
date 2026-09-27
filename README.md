# DemandOps (repo: KagFint)

Quick-Commerce Demand & Inventory Decision Platform — a production-quality
portfolio project covering data validation, SQL analytics, time-series
forecasting, stockout risk, recommendations, a what-if simulator, an API, and
a dashboard.

**Status: Checkpoint 02 — dataset acquired; ingestion + validation layer built
and run.** Real profile: 4.0M daily sales rows, 7 warehouses, 2020-08-01 →
2024-06-02, 5,390 product-warehouse series. First validation run: overall WARN
(52 null target rows; 61 missing calendar days across 2 warehouses; 32 rows
with corrupt discount fractions; 42 metadata-only inventory ids) — all
quantified in `docs/DATASET.md`, evidence in `data_quality_reports/`.

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
