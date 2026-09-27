-- Q: Which warehouses drive total demand, and how do orders translate to units?
-- Feeds: executive overview (Layer 8), warehouse ranking.
-- NOTE: total_orders carries minor intra-day variation across product rows
-- (1-4 distinct values per warehouse-day), so it is aggregated to its mean per
-- warehouse-day. Units and orders are aggregated separately, then joined.
WITH wh_day AS (
    SELECT warehouse, date, avg(total_orders) AS total_orders
    FROM rohlik.sales_train
    GROUP BY warehouse, date
),
units AS (
    SELECT warehouse,
           count(DISTINCT date)         AS days_covered,
           sum(sales)                   AS total_units_sold
    FROM rohlik.sales_train
    GROUP BY warehouse
),
orders AS (
    SELECT warehouse, sum(total_orders) AS total_orders
    FROM wh_day
    GROUP BY warehouse
)
SELECT u.warehouse,
       u.days_covered,
       round(u.total_units_sold::numeric, 0)  AS total_units_sold,
       round(o.total_orders::numeric, 0)      AS total_orders,
       round((u.total_units_sold / NULLIF(o.total_orders, 0))::numeric, 3) AS units_per_order
FROM units u
JOIN orders o USING (warehouse)
ORDER BY total_units_sold DESC;
