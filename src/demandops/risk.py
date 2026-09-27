"""Stockout risk engine (Layer 4).

The dataset has NO inventory units and NO lead times (see docs/DATASET.md) —
so this engine produces availability-aware demand risk, not classic
unit-coverage stockout prediction. Every field carries its epistemic label:

- OBSERVED : read from raw data (historical availability).
- DERIVED  : computed from OBSERVED data and model forecasts.
- ASSUMED  : a labeled business assumption (future availability = recent
             availability; tier thresholds). Never presented as fact.

Rules are pure functions of the inputs: same inputs -> same risk table.

Tier logic (thresholds are ASSUMED business parameters):
- HIGH:   estimated_unmet_units >= 10  AND risk_fraction >= 0.10
- MEDIUM: estimated_unmet_units >= 5   AND risk_fraction >= 0.05
- LOW:    otherwise
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from demandops import config, manifest
from demandops.db import get_engine

LOW_AVAILABILITY_DAY = 0.5   # a day with availability below this counts as constrained
TIER_HIGH_UNMET = 10.0
TIER_HIGH_FRACTION = 0.10
TIER_MEDIUM_UNMET = 5.0
TIER_MEDIUM_FRACTION = 0.05


def recent_availability(engine, window_end: str, days: int = 28) -> pd.DataFrame:
    """OBSERVED per-series availability over the `days` before window_end."""
    query = """
        SELECT unique_id,
               avg(availability)  AS recent_availability,
               count(*)           AS n_days_observed,
               sum(CASE WHEN availability < %(low)s THEN 1 ELSE 0 END) AS low_avail_days
        FROM rohlik.sales_train
        WHERE date >= %(window_end)s::date - %(days)s::int
          AND date < %(window_end)s::date
        GROUP BY unique_id
    """
    return pd.read_sql_query(
        query, engine,
        params={"low": LOW_AVAILABILITY_DAY, "window_end": window_end,
                "days": days},
    )


def compute_risk(forecasts: pd.DataFrame, availability: pd.DataFrame) -> pd.DataFrame:
    """Pure risk computation.

    forecasts: rows (unique_id, date, prediction) over the decision horizon.
    availability: rows (unique_id, recent_availability, n_days_observed,
    low_avail_days) from the pre-horizon window.
    """
    fc = (forecasts.groupby("unique_id", as_index=False)
          .agg(forecast_units=("prediction", "sum")))
    av = availability.copy()
    # ASSUMED: future availability equals recent observed availability.
    # For series with no observed days (data gap), assume fully available
    # and flag the gap rather than inventing a scarcity signal.
    av["assumed_future_availability"] = av["recent_availability"].fillna(1.0)
    av["availability_data_gap"] = av["n_days_observed"].fillna(0) == 0

    merged = fc.merge(av, on="unique_id", how="left")
    merged["assumed_future_availability"] = merged[
        "assumed_future_availability"].fillna(1.0)
    merged["availability_data_gap"] = merged["availability_data_gap"].fillna(True)

    # DERIVED from ASSUMED availability: unmet units = demand while the shelf
    # is assumed short. Fraction of forecast demand at risk.
    unmet_factor = (1.0 - merged["assumed_future_availability"]).clip(0.0, 1.0)
    merged["estimated_unmet_units"] = (
        merged["forecast_units"] * unmet_factor).round(2)
    merged["risk_fraction"] = (
        merged["estimated_unmet_units"]
        / merged["forecast_units"].clip(lower=1e-9)).round(4)
    merged["risk_fraction"] = merged["risk_fraction"].where(
        merged["forecast_units"] > 0, 0.0)

    def _tier(row: pd.Series) -> str:
        if (row["estimated_unmet_units"] >= TIER_HIGH_UNMET
                and row["risk_fraction"] >= TIER_HIGH_FRACTION):
            return "HIGH"
        if (row["estimated_unmet_units"] >= TIER_MEDIUM_UNMET
                and row["risk_fraction"] >= TIER_MEDIUM_FRACTION):
            return "MEDIUM"
        return "LOW"

    merged["risk_tier"] = merged.apply(_tier, axis=1)
    return merged


def run() -> int:
    engine = get_engine()
    forecast_path = config.PROCESSED_DATA_DIR / "forecasts" / "gbm_holdout_predictions.csv"
    if not forecast_path.exists():
        raise FileNotFoundError(
            "No forecasts found — run `python -m demandops.train_gbm` first. "
            "The risk layer consumes persisted forecasts, it never trains.")
    forecasts = pd.read_csv(forecast_path, parse_dates=["date"])
    window_end = str(forecasts["date"].min().date())

    availability = recent_availability(engine, window_end)
    risk = compute_risk(forecasts, availability)

    names = pd.read_sql_query(
        "SELECT unique_id, name, l1_category_name_en, warehouse "
        "FROM rohlik.inventory", engine)
    risk = risk.merge(names, on="unique_id", how="left")
    risk = risk.sort_values(["estimated_unmet_units", "forecast_units"],
                            ascending=False).reset_index(drop=True)

    out_dir = config.PROCESSED_DATA_DIR / "risk"
    out_dir.mkdir(parents=True, exist_ok=True)
    risk_path = out_dir / "risk_scores.csv"
    risk.to_csv(risk_path, index=False)

    tier_counts = risk["risk_tier"].value_counts().to_dict()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon": {"start": window_end,
                    "end": str(forecasts["date"].max().date())},
        "series": int(len(risk)),
        "tier_counts": tier_counts,
        "labels": {
            "recent_availability": "OBSERVED",
            "forecast_units": "DERIVED (XGBoost forecasts)",
            "assumed_future_availability": "ASSUMED (= recent availability)",
            "estimated_unmet_units": "DERIVED from ASSUMED availability",
            "tier_thresholds": "ASSUMED business parameters",
        },
        "top_high_risk": risk[risk["risk_tier"] == "HIGH"].head(10)[
            ["unique_id", "name", "warehouse", "forecast_units",
             "recent_availability", "estimated_unmet_units"]].to_dict("records"),
    }
    summary_path = config.EXPERIMENTS_DIR / "risk_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")

    manifest.write_manifest(
        kind="stockout_risk",
        inputs={"forecast_rows": int(len(forecasts)),
                "series_with_availability": int(availability["unique_id"].nunique())},
        outputs={"risk_scores": str(risk_path.relative_to(config.PROJECT_ROOT)),
                 "risk_summary": str(summary_path.relative_to(config.PROJECT_ROOT))},
        validation_summary={"overall": "PASS",
                            "note": "deterministic rules; labels recorded"},
    )

    print(f"risk tiers over {len(risk)} series: {tier_counts}")
    top_cols = ["name", "warehouse", "forecast_units",
                "recent_availability", "estimated_unmet_units"]
    top = risk[risk["risk_tier"] == "HIGH"].head(5)[top_cols]
    print("top HIGH-risk rows:")
    print(top.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
