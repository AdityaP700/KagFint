-- Q: Do named holidays change demand?
-- Feeds: holiday seasonality features, holiday uplift in recommendations.
SELECT c.holiday_name,
       count(*)                              AS n_observations,
       round(avg(s.sales)::numeric, 2)       AS avg_sales_on_holiday,
       round((avg(s.sales) / NULLIF(avg(CASE WHEN c.holiday = 0 THEN s.sales END), 0)
              - 1)::numeric, 3)              AS uplift_vs_nonholiday
FROM rohlik.sales_train s
JOIN rohlik.calendar c ON c.warehouse = s.warehouse AND c.date = s.date
WHERE c.holiday = 1 AND c.holiday_name IS NOT NULL
GROUP BY c.holiday_name
HAVING count(*) >= 500
ORDER BY n_observations DESC;
