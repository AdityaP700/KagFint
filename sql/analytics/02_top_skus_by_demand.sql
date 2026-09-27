-- Q: Which products sell the most units overall?
-- Feeds: assortment prioritization, top-SKU tracking.
SELECT i.name, i.warehouse, i.l1_category_name_en,
       round(sum(s.sales)::numeric, 0) AS total_units,
       round(avg(s.sell_price_main)::numeric, 2) AS avg_price
FROM rohlik.sales_train s
JOIN rohlik.inventory i USING (unique_id)
GROUP BY i.name, i.warehouse, i.l1_category_name_en
ORDER BY total_units DESC
LIMIT 30;
