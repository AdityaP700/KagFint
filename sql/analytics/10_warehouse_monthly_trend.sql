-- Q: How is each warehouse's demand trending month over month?
-- Feeds: hub-level demand trends; growth storyline for the dashboard.
-- Units and orders aggregated at their own grain, then joined.
WITH wh_day AS (
    SELECT warehouse, date, avg(total_orders) AS total_orders
    FROM rohlik.sales_train
    GROUP BY warehouse, date
),
monthly_units AS (
    SELECT warehouse, date_trunc('month', date)::date AS month, sum(sales) AS monthly_units
    FROM rohlik.sales_train
    GROUP BY warehouse, month
),
monthly_orders AS (
    SELECT warehouse, date_trunc('month', date)::date AS month, avg(total_orders) AS avg_daily_orders
    FROM wh_day
    GROUP BY warehouse, month
)
SELECT u.warehouse, u.month,
       round(u.monthly_units::numeric, 0)       AS monthly_units,
       round(o.avg_daily_orders::numeric, 0)    AS avg_daily_orders
FROM monthly_units u
JOIN monthly_orders o USING (warehouse, month)
ORDER BY u.warehouse, u.month;
