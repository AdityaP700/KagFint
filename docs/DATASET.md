# Dataset: Rohlik Sales Forecasting Challenge v2 (Kaggle)

Source: `kaggle competitions download -c rohlik-sales-forecasting-challenge-v2`
Downloaded 2026-09-27 into `data/raw/rohlik-sales-forecasting-challenge-v2/` (immutable).
Zip (47.3 MB) is kept alongside the extracted CSVs as the provenance artifact.

## Tables (verified from the actual files, not the description)

| table | rows | columns | granularity |
|---|---:|---|---|
| `sales_train` | 4,007,419 | 14 | daily, `unique_id` × `date`, 2020-08-01 → 2024-06-02 |
| `sales_test` | 47,021 | 12 | daily, 2024-06-03 → 2024-06-30 (28-day horizon), no `sales`/`availability` |
| `inventory` | 5,432 | 8 | one row per `unique_id` (product × warehouse) |
| `calendar` | 23,016 | 7 | `warehouse` × `date` holiday/closure flags |
| `test_weights` | 5,390 | 2 | per-series WMAPE weight (competition metric) |
| `solution` | 47,021 | 2 | all-zero submission placeholder (not used) |

7 warehouses: Prague_1, Prague_2, Prague_3, Brno_1, Budapest_1, Frankfurt_1, Munich_1.
5,390 series in train; `unique_id` = product-warehouse combination.

## Key columns (`sales_train`)

- `sales` — target, units sold. No negatives. 52 nulls (0.0013%).
- `availability` — fraction of the day the product was in stock (1.0 = full).
  **This is an OBSERVED stockout signal, not inventory units.** Stockout-risk
  (Layer 4) will derive coverage-based risk from it; no inventory-unit data
  exists and none will be fabricated.
- `total_orders` — warehouse-level daily order volume. 52 nulls.
- `sell_price_main` — list price; `type_0..6_discount` — discount fractions.

## Validation findings (first full run, 2026-09-27)

Overall status: **WARN** (no FAILs). Evidence in `data_quality_reports/`.

1. **`sales`/`total_orders` nulls**: 52 rows each — quantified, rows preserved.
2. **Date gaps**: Frankfurt_1 missing 53 calendar days, Munich_1 missing 8 days
   within their observed ranges. Real gaps in the raw data — flagged, not filled.
3. **Discount corruption**: 32 rows (0.0008%) have discount fractions outside
   [0,1] — including values as low as **-20.9** (Budapest_1, Munich_1, Prague_2).
   Sparse → WARN. Rows are preserved; downstream feature engineering must
   document its handling (e.g. clipping) explicitly — silently dropping them is
   forbidden. A material share (>0.1%) would escalate to FAIL.
4. **Inventory superset**: 42 inventory `unique_id`s (of 5,432) appear in
   neither train nor test — metadata-only products. Hard direction (every
   sales id has metadata) passes.
5. `calendar.holiday_name` is null exactly when `holiday == 0` — nullable by
   design, does not escalate.

## Known limitations

- No inventory-on-hand units, no lead times, no replenishment records. Layer 4
  therefore produces availability-aware demand risk, not classic unit-coverage
  stockout prediction. Assumptions will be labeled ASSUMED vs OBSERVED.
- Test-period `sales` are not public (placeholder solution); honest evaluation
  uses temporal splits out of the train range only.
