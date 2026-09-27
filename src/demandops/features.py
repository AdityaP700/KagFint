"""Leak-safe feature construction for gradient-boosted forecasting.

Leakage policy (each feature answers: would this be known at prediction time?):
- Lags (28/35/42/56) and rolling means are shifted by >= 28 days, so for any
  horizon date d every value comes from before the temporal cutoff. This makes
  the construction leak-proof for the 28-day horizon BY DESIGN.
- sell_price_main and discount columns at date d are treated as known: the
  competition provides them for the test period (they are set by the retailer
  in advance).
- Calendar flags (holidays, closures) are known in advance.
- total_orders at date d is EXCLUDED: although the competition supplies it for
  the test period, a real demand planner would not know a warehouse's daily
  order total in advance. Conservative choice, documented.
- availability at date d is EXCLUDED: it is an observed outcome of stockouts,
  not a known input.

Missing values (NaN lags for cold-start series, gaps) are kept, not dropped:
XGBoost routes missing values natively, which also covers zero-history series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from demandops.db import get_engine

LAGS = (28, 35, 42, 56)
ROLLING_WINDOWS = (7, 28)
LAG_SHIFT = 28  # all rolling windows end at (d - LAG_SHIFT)
HORIZON_DAYS = 28

DISCOUNT_COLS = [f"type_{i}_discount" for i in range(7)]


def load_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    engine = get_engine()
    df = pd.read_sql_query(
        "SELECT unique_id, date, warehouse, sales, sell_price_main, "
        + ", ".join(DISCOUNT_COLS)
        + " FROM rohlik.sales_train",
        engine, parse_dates=["date"],
    )
    cal = pd.read_sql_query(
        "SELECT warehouse, date, holiday, shops_closed, "
        "winter_school_holidays, school_holidays FROM rohlik.calendar",
        engine, parse_dates=["date"],
    )
    inv = pd.read_sql_query(
        "SELECT unique_id, l1_category_name_en FROM rohlik.inventory", engine)
    return df, cal, inv


def build_features(df: pd.DataFrame, cal: pd.DataFrame, inv: pd.DataFrame
                   ) -> tuple[pd.DataFrame, list[str]]:
    """Attach leak-safe features; returns (frame, feature_column_names)."""
    df = df.sort_values(["unique_id", "date"]).reset_index(drop=True)

    # Wide sales matrix on the global daily grid: row shift == calendar-day
    # shift. Internal gaps are forward-filled (documented raw data gaps);
    # leading NaNs stay NaN (no history to learn from yet).
    wide = df.pivot(index="date", columns="unique_id", values="sales").sort_index()
    wide_ffilled = wide.ffill()

    lag_frames: dict[str, pd.Series] = {}
    for k in LAGS:
        lag_frames[f"lag_{k}"] = wide_ffilled.shift(k).stack()
    for w in ROLLING_WINDOWS:
        lag_frames[f"rmean_{w}_lag28"] = (
            wide_ffilled.rolling(w, min_periods=7).mean().shift(LAG_SHIFT).stack()
        )
    feats = pd.DataFrame(lag_frames)
    feats.index = feats.index.set_names(["date", "unique_id"])
    df = df.merge(feats.reset_index(), on=["date", "unique_id"], how="left")

    df["discount_total"] = df[DISCOUNT_COLS].sum(axis=1)
    df = df.merge(cal, on=["warehouse", "date"], how="left")
    df = df.merge(inv, on="unique_id", how="left")
    df["dow"] = df["date"].dt.dayofweek
    df["day_of_month"] = df["date"].dt.day
    df["month"] = df["date"].dt.month

    # One-hot encode, but keep the raw warehouse column: per-warehouse metric
    # breakdowns need it, and it is not a model feature itself.
    dummies = pd.get_dummies(
        df[["warehouse", "l1_category_name_en"]], dtype="uint8")
    df = pd.concat([df.drop(columns=["l1_category_name_en"]), dummies], axis=1)

    feature_cols = [c for c in df.columns if c.startswith("lag_")
                    or c.startswith("rmean_")
                    or c in ("sell_price_main", "discount_total", "dow",
                             "day_of_month", "month", "holiday", "shops_closed",
                             "winter_school_holidays", "school_holidays")
                    or c.startswith("warehouse_")
                    or c.startswith("l1_category_name_en_")]
    return df, feature_cols


def temporal_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(inner_train, inner_validation, holdout) by date.

    inner_validation is the 28 days before the holdout: it exists only for
    early stopping / hyperparameter sanity, never for final metric claims.
    The holdout (final 28 days) is touched exactly once, at final evaluation.
    """
    max_date = df["date"].max()
    cutoff = max_date - pd.Timedelta(days=HORIZON_DAYS - 1)
    val_start = cutoff - pd.Timedelta(days=HORIZON_DAYS)
    inner_train = df[df["date"] < val_start]
    inner_val = df[(df["date"] >= val_start) & (df["date"] < cutoff)]
    holdout = df[df["date"] >= cutoff]
    return inner_train, inner_val, holdout
