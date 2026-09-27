-- Q: How does demand differ across price bands?
-- Feeds: price-tier view of the assortment; simulator context.
SELECT CASE
           WHEN sell_price_main < 2 THEN 'a_under_2'
           WHEN sell_price_main < 5 THEN 'b_2_to_5'
           WHEN sell_price_main < 15 THEN 'c_5_to_15'
           WHEN sell_price_main < 50 THEN 'd_15_to_50'
           ELSE 'e_over_50'
       END AS price_band,
       count(*)                      AS n_observations,
       round(avg(sales)::numeric, 2) AS avg_daily_sales_per_sku
FROM rohlik.sales_train
WHERE sell_price_main > 0
GROUP BY price_band
ORDER BY price_band;
