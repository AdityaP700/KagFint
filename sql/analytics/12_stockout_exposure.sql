-- Q: Where and when is stockout exposure worst (lowest availability)?
-- Feeds: stockout risk (Layer 4). availability is OBSERVED stock signal.
SELECT s.warehouse,
       i.l1_category_name_en AS category,
       count(*) FILTER (WHERE s.availability < 0.5) AS low_availability_rows,
       count(*) AS n_rows,
       round(avg(s.availability)::numeric, 3) AS avg_availability
FROM rohlik.sales_train s
JOIN rohlik.inventory i USING (unique_id)
GROUP BY s.warehouse, category
ORDER BY low_availability_rows DESC
LIMIT 25;
