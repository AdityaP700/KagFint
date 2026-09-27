-- Q: Which fast-moving SKUs are currently most at risk (high recent velocity,
--    recent availability failures)?
-- Feeds: stockout risk shortlist (Layer 4) -> recommendations (Layer 5).
WITH recent AS (
    SELECT unique_id, warehouse,
           avg(sales) FILTER (WHERE date > '2024-05-01') AS recent_daily_velocity,
           avg(availability) FILTER (WHERE date > '2024-05-01') AS recent_availability,
           count(*) FILTER (WHERE date > '2024-05-01' AND availability < 0.5) AS low_avail_days
    FROM rohlik.sales_train
    WHERE date > '2024-04-01'
    GROUP BY unique_id, warehouse
)
SELECT r.unique_id, i.name, r.warehouse,
       round(r.recent_daily_velocity::numeric, 2)  AS recent_daily_velocity,
       round(r.recent_availability::numeric, 3)    AS recent_availability,
       r.low_avail_days
FROM recent r
JOIN rohlik.inventory i USING (unique_id)
WHERE r.recent_daily_velocity > 10 AND r.low_avail_days > 0
ORDER BY r.low_avail_days DESC, r.recent_daily_velocity DESC
LIMIT 40;
