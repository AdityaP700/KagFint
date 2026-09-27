-- Q: How much extra demand do promotions generate?
-- Feeds: promo-aware features; what-if simulator (promotion toggle).
WITH flagged AS (
    SELECT s.*,
           (s.type_0_discount > 0 OR s.type_1_discount > 0 OR s.type_2_discount > 0
            OR s.type_3_discount > 0 OR s.type_4_discount > 0 OR s.type_5_discount > 0
            OR s.type_6_discount > 0) AS any_promo
    FROM rohlik.sales_train s
)
SELECT any_promo,
       count(*)                        AS n_observations,
       round(avg(sales)::numeric, 2)   AS avg_sales_per_sku,
       round(avg(sell_price_main)::numeric, 2) AS avg_list_price
FROM flagged
GROUP BY any_promo
ORDER BY any_promo;
