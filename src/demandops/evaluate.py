"""Temporal-split evaluation of baseline forecasts.

Protocol (per docs/DATASET.md and the competition setup):
- Horizon: the final 28 days of the training data (2024-05-06 → 2024-06-02),
  matching sales_test's 28-day horizon.
- Models see ONLY data before the horizon (no leakage by construction).
- Metrics: WMAPE (both unweighted and competition-weighted via
  rohlik.test_weights), MAE, RMSE — overall and per warehouse.
- Results land in experiments/ and a run manifest is written. Baseline
  numbers are preserved so the upcoming LightGBM model is judged against them.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

from demandops import config, manifest, metrics
from demandops.baselines import moving_average, seasonal_naive
from demandops.db import get_engine, psycopg_conninfo

HORIZON_DAYS = 28
WINDOW_MA = 28


def load_holdout_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load (history, holdout) where history is everything before the horizon.

    The horizon is exactly HORIZON_DAYS days ending at the data's max date.
    """
    engine = get_engine()
    with engine.connect() as conn:
        max_date = pd.Timestamp(conn.exec_driver_sql(
            "SELECT max(date) FROM rohlik.sales_train").scalar())
    cutoff = max_date - pd.Timedelta(days=HORIZON_DAYS - 1)
    history = pd.read_sql_query(
        "SELECT unique_id, date, warehouse, sales, total_orders, availability "
        "FROM rohlik.sales_train WHERE date < %(cutoff)s",
        engine, params={"cutoff": cutoff}, parse_dates=["date"],
    )
    holdout = pd.read_sql_query(
        "SELECT unique_id, date, warehouse, sales "
        "FROM rohlik.sales_train WHERE date >= %(cutoff)s",
        engine, params={"cutoff": cutoff}, parse_dates=["date"],
    )
    return history, holdout


def load_weights() -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT unique_id, weight FROM rohlik.test_weights", get_engine())


def evaluate(predictions: pd.DataFrame, holdout: pd.DataFrame,
             weights: pd.DataFrame) -> dict:
    merged = holdout.merge(predictions, on=["unique_id", "date"], how="left")
    if merged["prediction"].isna().any():
        raise RuntimeError(
            f"{int(merged['prediction'].isna().sum())} holdout rows lack a "
            "prediction — evaluation would be silently incomplete")

    w_map = weights.set_index("unique_id")["weight"]
    merged["weight"] = merged["unique_id"].map(w_map)

    overall = {
        "wmape": metrics.wmape(merged["sales"], merged["prediction"]),
        "wmape_weighted": metrics.wmape(merged["sales"], merged["prediction"],
                                        merged["weight"].to_numpy()),
        "mae": metrics.mae(merged["sales"], merged["prediction"]),
        "rmse": metrics.rmse(merged["sales"], merged["prediction"]),
        "n_rows": int(len(merged)),
    }
    per_wh: dict[str, dict] = {}
    for wh, g in merged.groupby("warehouse"):
        per_wh[str(wh)] = {
            "wmape": metrics.wmape(g["sales"], g["prediction"]),
            "mae": metrics.mae(g["sales"], g["prediction"]),
            "rmse": metrics.rmse(g["sales"], g["prediction"]),
            "n_rows": int(len(g)),
        }
    return {"overall": overall, "per_warehouse": per_wh}


def run() -> int:
    experiments_dir = config.EXPERIMENTS_DIR
    experiments_dir.mkdir(parents=True, exist_ok=True)

    history, holdout = load_holdout_data()
    weights = load_weights()
    horizon_dates = sorted(holdout["date"].unique())
    horizon_dates = [pd.Timestamp(d) for d in horizon_dates]
    print(f"history rows: {len(history)}, holdout rows: {len(holdout)}, "
          f"horizon: {horizon_dates[0].date()} -> {horizon_dates[-1].date()}")

    results: dict[str, dict] = {}
    for name, preds in [
        ("seasonal_naive_7", seasonal_naive(history, horizon_dates,
                                            series_ids=holdout["unique_id"].unique())),
        ("moving_average_28", moving_average(history, horizon_dates, WINDOW_MA,
                                             series_ids=holdout["unique_id"].unique())),
    ]:
        fb_series = preds.attrs.get("fallback_series", 0)
        fb_rows = preds.attrs.get("fallback_rows", 0)
        zh_series = preds.attrs.get("zero_history_series", 0)
        note = ""
        if fb_series:
            note += f" [cold-start fallback: {fb_series} series / {fb_rows} rows]"
        if zh_series:
            note += f" [zero-history series: {zh_series} (global-mean fill)]"
        print(f"evaluating {name}{note} ...")
        results[name] = evaluate(preds, holdout, weights)
        if fb_series:
            results[name]["cold_start_fallback"] = {
                "series": fb_series, "rows": fb_rows}
        if zh_series:
            results[name]["zero_history_fallback"] = {
                "series": zh_series,
                "global_mean_used": preds.attrs.get("global_mean_used")}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "rohlik-sales-forecasting-challenge-v2",
        "split": {"type": "temporal", "horizon_days": HORIZON_DAYS,
                  "holdout_start": str(horizon_dates[0].date()),
                  "holdout_end": str(horizon_dates[-1].date())},
        "results": results,
    }
    out = experiments_dir / "baseline_results.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    manifest.write_manifest(
        kind="baseline_forecast",
        inputs={"history_rows": len(history), "holdout_rows": len(holdout),
                "series": int(history["unique_id"].nunique())},
        outputs={"baseline_results": str(out.relative_to(config.PROJECT_ROOT))},
        validation_summary={"overall": "PASS",
                            "note": "models evaluated on identical temporal split"},
    )

    for name, r in results.items():
        o = r["overall"]
        print(f"{name}: WMAPE={o['wmape']:.4f}  wWMAPE={o['wmape_weighted']:.4f}  "
              f"MAE={o['mae']:.3f}  RMSE={o['rmse']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
