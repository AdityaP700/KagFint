# DemandOps — Executive Overview

Quick-commerce demand and inventory decisions for the Rohlik dataset:
7 warehouses, 5,390 product series, forecasts and stockout risk for the next
28 days. Pipeline-validated data only.

```sql warehouse_demand
SELECT warehouse,
       count(DISTINCT unique_id)       AS products,
       sum(sales)                      AS total_units,
       avg(availability)::numeric(4,3) AS avg_availability
FROM rohlik.sales_train
GROUP BY warehouse
ORDER BY total_units DESC
```

<BigValue
    data={warehouse_demand}
    value=total_units
    name="Total units sold (all warehouses, 2020–2024)"
/>

<BarChart
    data={warehouse_demand}
    x=warehouse
    y=total_units
    title="Total demand by warehouse"
/>

```sql availability_by_warehouse
SELECT warehouse,
       avg(availability)::numeric(4,3) AS avg_availability,
       sum(CASE WHEN availability < 0.5 THEN 1 ELSE 0 END) AS constrained_days
FROM rohlik.sales_train
GROUP BY warehouse
ORDER BY avg_availability
```

<BarChart
    data={availability_by_warehouse}
    x=warehouse
    y=constrained_days
    title="Low-availability product-days by warehouse (the stockout footprint)"
/>

The warehouse with the most constrained product-days is not necessarily the
largest one — availability, not size, is where the recoverable demand is.
