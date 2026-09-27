-- Q: How much does the assortment churn (new products appearing over time)?
-- Feeds: cold-start awareness; explains series-count growth.
SELECT date_trunc('quarter', first_seen)::date AS quarter,
       count(*) AS n_products_introduced
FROM (
    SELECT unique_id, min(date) AS first_seen
    FROM rohlik.sales_train
    GROUP BY unique_id
) t
GROUP BY quarter
ORDER BY quarter;
