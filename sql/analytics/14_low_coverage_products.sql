-- Q: Which products have too little history to forecast reliably?
-- Feeds: model coverage gating; honest forecast scope.
WITH coverage AS (
    SELECT unique_id,
           count(*)                AS n_days,
           min(date)               AS first_seen,
           max(date)               AS last_seen,
           max(date) - min(date)   AS span_days
    FROM rohlik.sales_train
    GROUP BY unique_id
)
SELECT CASE
           WHEN n_days < 30 THEN 'a_under_30d'
           WHEN n_days < 180 THEN 'b_under_180d'
           WHEN n_days < 730 THEN 'c_under_2y'
           ELSE 'd_full_history'
       END AS coverage_band,
       count(*) AS n_products
FROM coverage
GROUP BY coverage_band
ORDER BY coverage_band;
