-- Q: Which SKUs have the most erratic demand (coefficient of variation)?
-- Feeds: volatility-aware forecasting and safety-stock thinking.
-- Volume filter (>1000 units lifetime) avoids noise from near-zero SKUs.
WITH per_sku AS (
    SELECT i.name, i.warehouse,
           count(*)            AS n_days,
           sum(s.sales)        AS total_units,
           avg(s.sales)        AS mean_sales,
           stddev_pop(s.sales) AS sd_sales
    FROM rohlik.sales_train s
    JOIN rohlik.inventory i USING (unique_id)
    GROUP BY i.name, i.warehouse
    HAVING sum(s.sales) > 1000
)
SELECT name, warehouse, n_days, round(total_units::numeric, 0) AS total_units,
       round(mean_sales::numeric, 2)  AS mean_daily_sales,
       round(sd_sales::numeric, 2)    AS sd_daily_sales,
       round((sd_sales / NULLIF(mean_sales, 0))::numeric, 3) AS coeff_of_variation
FROM per_sku
ORDER BY coeff_of_variation DESC
LIMIT 30;
