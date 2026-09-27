# Stockout Risk & Recommended Actions

Risk scores over the next 28 days, produced by the pipeline's risk engine.
Labels: forecast demand is DERIVED (XGBoost), recent availability is OBSERVED,
future availability is ASSUMED to equal recent availability.

```sql high_risk
SELECT name, warehouse,
       round(forecast_units::numeric, 0)        AS forecast_units_28d,
       round(recent_availability::numeric, 3)   AS observed_availability,
       round(estimated_unmet_units::numeric, 0) AS estimated_unmet_units
FROM bi.risk_scores
WHERE risk_tier = 'HIGH' AND NOT availability_data_gap
ORDER BY estimated_unmet_units DESC
LIMIT 25
```

<DataTable data={high_risk} search=true/>

```sql tier_counts
SELECT risk_tier, count(*) AS series
FROM bi.risk_scores
GROUP BY risk_tier
ORDER BY series DESC
```

<BarChart data={tier_counts} x=risk_tier y=series title="Series by risk tier" />

```sql action_counts
SELECT action, count(*) AS series, sum(recommended_units) AS total_units_to_order
FROM bi.recommendations
GROUP BY action
ORDER BY total_units_to_order DESC
```

<DataTable data={action_counts} />

Every recommended quantity embeds a labeled +10% safety margin and pack size 5
(ASSUMED business parameters — see `src/demandops/recommendations.py`).
