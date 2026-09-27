-- Q: How many units were plausibly lost to low-availability days?
-- Feeds: sizing the value of fixing stockouts (upper-bound estimate).
-- ASSUMPTION: on low-availability days, demand would have been the SKU's own
-- average non-constrained daily sales. This is an estimate, not an observation.
WITH baseline AS (
    SELECT unique_id, avg(sales) AS unconstrained_avg
    FROM rohlik.sales_train
    WHERE availability >= 0.95
    GROUP BY unique_id
)
SELECT s.warehouse,
       round(sum(greatest(b.unconstrained_avg - s.sales, 0))::numeric, 0) AS estimated_lost_units
FROM rohlik.sales_train s
JOIN baseline b USING (unique_id)
WHERE s.availability < 0.5
GROUP BY s.warehouse
ORDER BY estimated_lost_units DESC;
