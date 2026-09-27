-- Q: Is basket composition changing (units sold per warehouse order)?
-- Feeds: interpreting order volume vs unit demand divergence.
-- Units and orders aggregated at their own grain, then joined.
WITH wh_day AS (
    SELECT warehouse, date, avg(total_orders) AS total_orders
    FROM rohlik.sales_train
    WHERE total_orders > 0
    GROUP BY warehouse, date
),
quarterly_units AS (
    SELECT warehouse, date_trunc('quarter', date)::date AS quarter, sum(sales) AS units
    FROM rohlik.sales_train
    GROUP BY warehouse, quarter
),
quarterly_orders AS (
    SELECT warehouse, date_trunc('quarter', date)::date AS quarter, sum(total_orders) AS orders
    FROM wh_day
    GROUP BY warehouse, quarter
)
SELECT u.warehouse, u.quarter,
       round((u.units / NULLIF(o.orders, 0))::numeric, 3) AS units_per_order
FROM quarterly_units u
JOIN quarterly_orders o USING (warehouse, quarter)
ORDER BY u.quarter, u.warehouse;
