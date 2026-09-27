-- Q: Which categories generate the most demand?
-- Feeds: category-level planning; dashboard breakdowns.
SELECT coalesce(i.l1_category_name_en, 'UNKNOWN') AS category,
       count(DISTINCT i.unique_id)          AS n_products,
       round(sum(s.sales)::numeric, 0)      AS total_units,
       round(avg(s.sell_price_main)::numeric, 2) AS avg_price
FROM rohlik.sales_train s
JOIN rohlik.inventory i USING (unique_id)
GROUP BY category
ORDER BY total_units DESC;
