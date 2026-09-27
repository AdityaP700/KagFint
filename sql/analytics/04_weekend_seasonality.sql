-- Q: How does demand vary by day of week?
-- Feeds: weekly seasonality features (Layer 3), staffing plans.
-- Sales averaged at product grain; orders at warehouse-day grain (aggregated
-- separately to avoid product-row weighting).
WITH sales_dow AS (
    SELECT extract(dow FROM date)::int AS day_of_week,
           count(*)                    AS n_observations,
           avg(sales)                  AS avg_sales_per_sku
    FROM rohlik.sales_train
    GROUP BY day_of_week
),
orders_dow AS (
    SELECT extract(dow FROM date)::int AS day_of_week,
           avg(total_orders)           AS avg_daily_orders_per_wh
    FROM (
        SELECT warehouse, date, avg(total_orders) AS total_orders
        FROM rohlik.sales_train
        GROUP BY warehouse, date
    ) wh_day
    GROUP BY day_of_week
)
SELECT s.day_of_week,
       s.n_observations,
       round(s.avg_sales_per_sku::numeric, 2)  AS avg_daily_sales_per_sku,
       round(o.avg_daily_orders_per_wh::numeric, 0) AS avg_daily_orders_per_wh
FROM sales_dow s
JOIN orders_dow o USING (day_of_week)
ORDER BY s.day_of_week;
