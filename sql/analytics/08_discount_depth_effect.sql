-- Q: Does deeper discounting monotonically increase unit demand?
-- Feeds: discount-response curves for the what-if simulator.
-- Excludes the 32 corrupt rows (discount outside [0,1]) documented in
-- docs/DATASET.md finding 3 — quantified exclusion, not silent cleaning.
SELECT CASE
           WHEN total_discount <= 0 THEN '0_no_promo'
           WHEN total_discount < 0.10 THEN '1_shallow'
           WHEN total_discount < 0.25 THEN '2_moderate'
           WHEN total_discount < 0.50 THEN '3_deep'
           ELSE '4_very_deep'
       END AS discount_band,
       count(*)                      AS n_observations,
       round(avg(sales)::numeric, 2) AS avg_sales_per_sku
FROM (
    SELECT sales, (coalesce(type_0_discount, 0) + coalesce(type_1_discount, 0)
                 + coalesce(type_2_discount, 0) + coalesce(type_3_discount, 0)
                 + coalesce(type_4_discount, 0) + coalesce(type_5_discount, 0)
                 + coalesce(type_6_discount, 0)) AS total_discount
    FROM rohlik.sales_train
    WHERE type_0_discount BETWEEN 0 AND 1 AND type_1_discount BETWEEN 0 AND 1
      AND type_2_discount BETWEEN 0 AND 1 AND type_3_discount BETWEEN 0 AND 1
      AND type_4_discount BETWEEN 0 AND 1 AND type_5_discount BETWEEN 0 AND 1
      AND type_6_discount BETWEEN 0 AND 1
) t
GROUP BY discount_band
ORDER BY discount_band;
