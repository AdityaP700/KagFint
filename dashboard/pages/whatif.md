# What-If Simulation

Scenarios are computed by `src/demandops/simulator.py` over the frozen risk
table and land in the `bi` schema via `python -m demandops.bi_load`. The
baseline columns are the frozen pipeline output; scenario columns exist only
in simulation outputs — history is never modified.

```sql scenario_comparison
SELECT 'baseline' AS scenario, round(sum(estimated_unmet_units)::numeric, 0) AS unmet_units
FROM bi.risk_scores
UNION ALL
SELECT 'demand +20%, promos +35.6%, availability +0.10' AS scenario,
       round(sum(scenario_unmet_units)::numeric, 0) AS unmet_units
FROM bi.simulation_dm1p2_pu0p356_ai0p1
```

<BarChart
    data={scenario_comparison}
    x=scenario
    y=unmet_units
    title="Projected unmet units over the 28-day horizon"
/>

Reading: fixing 10 points of availability more than absorbs a simultaneous
demand surge and promotional lift on the current assortment. The promotion
elasticity (+35.6%) is DERIVED from our own aggregate SQL analysis and used as
an ASSUMED elasticity, not a causal promise.
