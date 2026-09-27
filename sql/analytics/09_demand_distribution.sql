-- Q: What does the distribution of daily per-SKU demand look like?
-- Feeds: choosing metrics (heavy right tail motivates WMAPE over RMSE).
SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY sales) AS p50,
       percentile_disc(0.75) WITHIN GROUP (ORDER BY sales) AS p75,
       percentile_disc(0.90) WITHIN GROUP (ORDER BY sales) AS p90,
       percentile_disc(0.99) WITHIN GROUP (ORDER BY sales) AS p99,
       round(max(sales)::numeric, 1) AS max_sales,
       round(avg(sales)::numeric, 2) AS mean_sales
FROM rohlik.sales_train;
