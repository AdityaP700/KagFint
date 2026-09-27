# SQL Analytics Catalog

Each query answers one identifiable business question. Run them all with
`PYTHONPATH=src .venv/Scripts/python.exe -m demandops.sql_runner` (sequential,
single connection). Outputs land in `data/processed/analytics/*.csv`; every
batch writes a run manifest to `data_quality_reports/`.

| # | file | business question |
|---|------|-------------------|
| 01 | `01_top_warehouses_by_demand.sql` | Which warehouses drive total demand; units per order? |
| 02 | `02_top_skus_by_demand.sql` | Which products sell the most units? |
| 03 | `03_most_volatile_skus.sql` | Which SKUs have the most erratic demand (CV, volume-filtered)? |
| 04 | `04_weekend_seasonality.sql` | How does demand vary by day of week? |
| 05 | `05_holiday_uplift.sql` | Do named holidays change demand (uplift vs non-holiday)? |
| 06 | `06_shops_closed_impact.sql` | What happens to demand when shops are closed? |
| 07 | `07_promotion_uplift.sql` | How much extra demand do promotions generate? |
| 08 | `08_discount_depth_effect.sql` | Does deeper discounting increase demand monotonically? |
| 09 | `09_demand_distribution.sql` | What is the shape of per-SKU daily demand? |
| 10 | `10_warehouse_monthly_trend.sql` | How is each warehouse trending monthly? |
| 11 | `11_category_demand.sql` | Which categories generate the most demand? |
| 12 | `12_stockout_exposure.sql` | Where/when is availability-driven stockout exposure worst? |
| 13 | `13_lost_sales_estimate.sql` | How many units were plausibly lost to low-availability days? (ASSUMED-based estimate) |
| 14 | `14_low_coverage_products.sql` | Which products lack history for reliable forecasts? |
| 15 | `15_assortment_churn.sql` | How fast does the assortment churn (new product introductions)? |
| 16 | `16_high_risk_skus.sql` | Which fast-moving SKUs show recent availability failures? |
| 17 | `17_price_band_demand.sql` | How does demand differ across price bands? |
| 18 | `18_sales_per_order_trend.sql` | Is basket composition (units per order) changing? |

## Data-grain notes (documented decisions, not silent choices)

- `total_orders` varies slightly within a warehouse-day (1–4 distinct values
  across product rows; 17 warehouse-days all-null). Order-based queries
  aggregate it to its **mean per warehouse-day**, then aggregate orders
  separately from units — never summed across product rows.
- Query 08 excludes the 32 rows with discount fractions outside [0,1]
  (documented in `docs/DATASET.md`); the exclusion is explicit in the SQL.
- Query 13's lost-sales estimate is labeled ASSUMED: it uses each SKU's own
  unconstrained-day average as counterfactual demand — an upper-bound estimate.
