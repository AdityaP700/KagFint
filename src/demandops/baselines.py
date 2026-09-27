"""Baseline forecasting models.

Two deliberately simple yardsticks that any advanced model must beat on the
same temporal split. Both produce a flat DataFrame of
(unique_id, date, prediction) rows covering the full horizon for every series
present in the history.

Seasonal naive: prediction for day d = actual sales on day d-7, applied
recursively, which for a multi-week horizon is equivalent to tiling the final
7 days of history.

Moving average: the mean of the trailing `window` days of history, held flat
across the horizon.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _check_history(history: pd.DataFrame) -> None:
    required = {"unique_id", "date", "sales"}
    if not required.issubset(history.columns):
        raise ValueError(f"history must contain {sorted(required)}")
    if history.empty:
        raise ValueError("history is empty — nothing to forecast from")


# Null-fill rule (documented in docs/DATASET.md): the 52 raw nulls in sales
# are forward-filled within each series; leading nulls become 0 so that no
# NaN predictions are produced silently. Series are also reindexed to a
# gapless daily grid — some warehouses have missing calendar days (e.g.
# Frankfurt_1 has 53), and pattern extraction requires every weekday present.


def _regularize(history: pd.DataFrame) -> pd.DataFrame:
    """One row per unique_id per calendar day across each series' own range."""
    sales = history[["unique_id", "date", "sales"]].sort_values(["unique_id", "date"])

    def _fill(grp: pd.DataFrame) -> pd.DataFrame:
        idx = pd.date_range(grp["date"].min(), grp["date"].max(), freq="D")
        grid = grp.set_index("date").reindex(idx)
        # reindex creates NaN rows for gap days; re-stamp the series id so the
        # grid stays attributable to its series.
        grid["unique_id"] = grp["unique_id"].iloc[0]
        return grid.rename_axis("date").reset_index()

    out = (
        sales.groupby("unique_id", group_keys=False)[["unique_id", "date", "sales"]]
        .apply(_fill)
    )
    out["sales"] = out.groupby("unique_id")["sales"].ffill()
    out["sales"] = out["sales"].fillna(0.0)
    return out


def _grid(sales: pd.DataFrame, horizon_dates: list[pd.Timestamp],
          series_ids) -> pd.DataFrame:
    """Full (unique_id, date) forecast grid, including any caller-declared
    series that have no history rows (zero-history products)."""
    ids = set(sales["unique_id"].unique())
    if series_ids is not None:
        ids |= set(series_ids)
    future = pd.MultiIndex.from_product(
        [sorted(ids), horizon_dates], names=["unique_id", "date"]
    ).to_frame(index=False)
    future["dow"] = future["date"].dt.dayofweek
    return future


def seasonal_naive(history: pd.DataFrame, horizon_dates: list[pd.Timestamp],
                   series_ids=None) -> pd.DataFrame:
    _check_history(history)
    sales = _regularize(history)

    # Seasonal-naive with weekly lag over a multi-week horizon is the final
    # 7-day pattern repeated. Equivalent to recursive prediction(d) = pred(d-7).
    last_week = (
        sales.sort_values("date")
        .groupby("unique_id")
        .tail(7)
        .rename(columns={"sales": "prediction"})
    )
    dow_pattern = last_week.assign(dow=last_week["date"].dt.dayofweek)[
        ["unique_id", "dow", "prediction"]
    ]

    future = _grid(sales, horizon_dates, series_ids)
    out = future.merge(dow_pattern, on=["unique_id", "dow"], how="left")

    # Cold-start fallback (documented): series with < 7 days of history have no
    # full weekday pattern; their missing days fall back to that series' mean
    # of available days. Usage is reported in attrs, never hidden.
    n_dows = dow_pattern.groupby("unique_id")["dow"].nunique()
    incomplete = n_dows[n_dows < 7].index
    if len(incomplete):
        means = (sales[sales["unique_id"].isin(incomplete)]
                 .groupby("unique_id")["sales"].mean())
        mask = out["unique_id"].isin(incomplete) & out["prediction"].isna()
        out.loc[mask, "prediction"] = out.loc[mask, "unique_id"].map(means)
        out.attrs["fallback_series"] = int(len(incomplete))
        out.attrs["fallback_rows"] = int(mask.sum())

    # Zero-history series (documented): products whose first-ever sale falls
    # inside the horizon have no data at all; they receive the global mean of
    # historical sales. Reported, never hidden.
    zero_hist = int(out.loc[out["prediction"].isna(), "unique_id"].nunique())
    if zero_hist:
        global_mean = float(sales["sales"].mean())
        mask = out["prediction"].isna()
        out.loc[mask, "prediction"] = global_mean
        out.attrs["zero_history_series"] = zero_hist
        out.attrs["zero_history_rows"] = int(mask.sum())
        out.attrs["global_mean_used"] = global_mean
    if out["prediction"].isna().any():
        raise RuntimeError("seasonal naive produced NaN predictions — "
                           "fallback logic is incomplete")
    return out[["unique_id", "date", "prediction"]]


def moving_average(history: pd.DataFrame, horizon_dates: list[pd.Timestamp],
                   window: int = 28, series_ids=None) -> pd.DataFrame:
    _check_history(history)
    if window <= 0:
        raise ValueError("window must be positive")
    sales = _regularize(history)
    cutoff = sales["date"].max() - pd.Timedelta(days=window - 1)
    recent = sales[sales["date"] >= cutoff]
    means = recent.groupby("unique_id")["sales"].mean().rename("prediction").reset_index()
    future = _grid(sales, horizon_dates, series_ids)
    out = future.merge(means, on="unique_id", how="left")
    # Zero-history series (documented): see seasonal_naive. Global mean fill.
    zero_hist = int(out.loc[out["prediction"].isna(), "unique_id"].nunique())
    if zero_hist:
        global_mean = float(sales["sales"].mean())
        mask = out["prediction"].isna()
        out.loc[mask, "prediction"] = global_mean
        out.attrs["zero_history_series"] = zero_hist
        out.attrs["zero_history_rows"] = int(mask.sum())
        out.attrs["global_mean_used"] = global_mean
    if out["prediction"].isna().any():
        raise RuntimeError("moving average produced NaN predictions")
    return out[["unique_id", "date", "prediction"]]
