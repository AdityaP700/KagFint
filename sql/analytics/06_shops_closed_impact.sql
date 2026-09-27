-- Q: What happens to demand when Rohlik shops are closed?
-- Feeds: closure-aware forecasting; explains demand troughs.
SELECT c.shops_closed,
       count(*)                        AS n_observations,
       round(avg(s.sales)::numeric, 2) AS avg_sales_per_sku,
       round(avg(s.total_orders)::numeric, 0) AS avg_orders
FROM rohlik.sales_train s
JOIN rohlik.calendar c ON c.warehouse = s.warehouse AND c.date = s.date
GROUP BY c.shops_closed
ORDER BY c.shops_closed;
