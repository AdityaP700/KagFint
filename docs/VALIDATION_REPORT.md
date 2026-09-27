# VALIDATION_REPORT

Every number below was produced by code in this repository and is traceable to
a JSON artifact or a test. Nothing is cited from memory.

## 1. Dataset

| property | value |
|---|---|
| source | [Rohlik Sales Forecasting Challenge v2](https://www.kaggle.com/competitions/rohlik-sales-forecasting-challenge-v2), Kaggle |
| downloaded | 2026-09-27 via Kaggle CLI into `data/raw/` (47.3 MB zip, 299 MB extracted) |
| train rows | 4,007,419 |
| series | 5,390 product-warehouse combinations (`unique_id`) |
| warehouses | Prague_1, Prague_2, Prague_3, Brno_1, Budapest_1, Frankfurt_1, Munich_1 |
| date range | 2020-08-01 to 2024-06-02 (per-warehouse ranges differ: Frankfurt_1 has 855 days covered, Munich_1 1,102) |
| target | `sales` (daily units), no negatives, 52 nulls |
| known anomalies | see `docs/DATASET.md`: 52 null targets, 61 missing calendar days (Frankfurt_1 53, Munich_1 8), 32 corrupt discount fractions (min -20.9), 42 metadata-only inventory ids |

## 2. Validation checks

Runner: `PYTHONPATH=src python -m demandops.pipeline` (exits nonzero on FAIL).
Latest report: `data_quality_reports/validation_report_*.json` (one per run).

| check | scope | first real run |
|---|---|---|
| schema (columns + dtype families) | all 5 tables | PASS |
| missingness | all tables | WARN (52 null `sales`/`total_orders`) |
| duplicates (business keys) | all tables | PASS |
| date continuity (per warehouse) | dated tables | WARN (Frankfurt_1: 53 days, Munich_1: 8) |
| numeric sanity | sales, prices, availability, discounts | WARN (32 discount outliers, preserved) |
| referential integrity | sales/weights -> inventory | PASS |
| coverage (inventory superset) | inventory -> sales_train | WARN (42 metadata-only ids) |

Gate semantics: FAIL blocks downstream stages (nonzero exit); WARN requires
quantified evidence in the report; nothing is silently repaired.

## 3. Forecast split

- Temporal split, no shuffling. Holdout: **2024-05-06 to 2024-06-02** (final
  28 days, matching the competition horizon). Models see only pre-holdout data.
- Inner validation window (the 28 days before the holdout) is used solely for
  early stopping; the holdout is touched once, at final evaluation.
- Metrics: WMAPE (unweighted and competition-weighted via `rohlik.test_weights`),
  MAE, RMSE. Evaluator refuses to score if any holdout row lacks a prediction.

## 4. Models and results

### Baselines (`experiments/baseline_results.json`)

| model | WMAPE | weighted WMAPE | MAE | RMSE |
|---|---|---|---|---|
| seasonal_naive_7 | 0.3374 | 0.4734 | 39.49 | 124.43 |
| moving_average_28 | 0.3164 | 0.4130 | 37.03 | 118.26 |

Documented fallbacks: cold-start series (< 7d history): 6 series / 76 rows use
their own available-days mean; zero-history series use the global mean
(10 series for seasonal naive; 1,613 series without recent rows for the 28d
window, mostly discontinued).

### Gradient boosting (`experiments/gbm_results.json`)

| property | value |
|---|---|
| model | XGBoost 3.2.0, `tree_method=hist`, `device=cuda` (RTX 4050 Laptop) |
| features | 24 (lags 28/35/42/56, rolling means shifted 28d, price, discount total, calendar flags, warehouse/category one-hot) |
| training rows | 3,912,496 |
| selection | early stopping on inner validation -> 740 rounds; final fit on all pre-holdout data |
| holdout WMAPE | **0.2518** |
| holdout weighted WMAPE | **0.3174** |
| holdout MAE | 29.47 |
| holdout RMSE | 95.65 |
| seed | 42 (re-run reproduces metrics exactly) |

### Per-warehouse WMAPE (GBM)

| warehouse | WMAPE | MAE |
|---|---|---|
| Prague_1 | 0.2298 | 36.42 |
| Prague_3 | 0.2343 | 19.26 |
| Prague_2 | 0.2424 | 22.13 |
| Brno_1 | 0.2423 | 40.96 |
| Budapest_1 | 0.2784 | 29.86 |
| Munich_1 | 0.3159 | 41.57 |
| Frankfurt_1 | 0.3174 | 16.45 |

Best: Prague_1 (22.98%). Worst: Frankfurt_1 (31.74%), consistent with its
short, gap-riddled history. Top features by importance: `rmean_28_lag28`,
warehouse one-hots, `rmean_7_lag28`.

## 5. Risk and recommendation layers

- Risk: deterministic rules over forecasts + observed availability. Tiers on
  real data: HIGH 1,051 / MEDIUM 729 / LOW 1,959 (3,739 series). All fields
  labeled OBSERVED / DERIVED / ASSUMED (`experiments/risk_summary.json`).
- Recommendations: 1,051 replenish_now / 729 replenish_scheduled / 1,822
  monitor / 137 investigate_data. Engine version 1.0.0, rule IDs on every row
  (`experiments/recommendations_summary.json`).
- Simulator: identity scenario reproduces the risk table (delta 0 enforced at
  runtime); "demand x1.2, promos +35.6%, availability +0.10" yields unmet
  646,224 -> 325,017.

## 6. Test coverage

104 tests, all passing:

| area | count | what they prove |
|---|---|---|
| validation layer | 16 | dirty-data fixtures yield explicit FAIL/WARN with evidence |
| database integration | 4 | row counts, date bounds, referential integrity, value ranges |
| forecasting | 13 | metrics math, pattern tiling, gap repair, cold-start fallbacks |
| features | 5 | lag/rolling correctness, leakage-spike impossibility, split sizes |
| risk engine | 7 | tier boundaries, zero-demand/availability, determinism |
| recommendations | 30 | input contract, quantity invariants, degradation, audit fields |
| simulator | 13 | lever math, caps, baseline separation, invalid-scenario refusal |
| API | 15 | health, 404/422/503 contracts, filters, simulation, OpenAPI |
| dashboard | 2 | decision content present, self-contained (no external assets) |

## 7. Known limitations

- No inventory units or lead times in the data: risk is availability-aware,
  not unit-coverage replenishment.
- Zero-history products use a global-mean fallback (cold-start patch, not a
  solution; a category-level model is the honest fix).
- Daily batch forecasts; no streaming or intra-day retraining.
- 32 corrupt discount rows and 52 null-target rows are preserved, not removed;
  feature engineering documents its handling explicitly.
- Evidence.dev BI build is scaffolded but its SvelteKit prerender step is
  unfinished (see `dashboard/README.md`).

## 8. Reproducibility

1. `pip install -r requirements.txt` in a virtualenv (Python 3.11).
2. Kaggle download (one command, documented in README section 6).
3. Run the pipeline modules in the README's stated order; each writes a
   manifest to `data_quality_reports/`.
4. `pytest tests/ -q` runs the full suite (DB integration tests need
   `DATABASE_URL` and skip cleanly otherwise).
5. The GBM is seeded (`random_state=42`); re-runs reproduce holdout metrics.
