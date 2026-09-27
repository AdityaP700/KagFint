"""Tests for leak-safe feature construction on small synthetic data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from demandops.features import build_features, temporal_split


DAYS = 120


def make_inputs(spike_in_holdout: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2024-01-01", periods=DAYS)
    df = pd.DataFrame({
        "unique_id": 1,
        "date": dates,
        "warehouse": "W_1",
        "sales": 10.0,
        "sell_price_main": 5.0,
        **{f"type_{i}_discount": 0.0 for i in range(7)},
    })
    if spike_in_holdout:
        # A demand spike confined to the last 28 days (the holdout).
        df.loc[df["date"] >= dates[-28], "sales"] = 1000.0
    cal = pd.DataFrame({
        "warehouse": "W_1", "date": dates, "holiday": 0, "shops_closed": 0,
        "winter_school_holidays": 0, "school_holidays": 0,
    })
    inv = pd.DataFrame({"unique_id": [1], "l1_category_name_en": ["Bakery"]})
    return df, cal, inv


def test_lag_28_matches_sales_28_days_earlier():
    df, cal, inv = make_inputs()
    fdf, _ = build_features(df, cal, inv)
    row = fdf[fdf["date"] == fdf["date"].max()]
    expected = fdf.loc[fdf["date"] == fdf["date"].max() - pd.Timedelta(days=28), "sales"].iloc[0]
    assert row["lag_28"].iloc[0] == pytest.approx(expected)


def test_rolling_mean_window_is_shifted():
    df, cal, inv = make_inputs()
    fdf, _ = build_features(df, cal, inv)
    d = fdf["date"].max()
    # rmean_28_lag28 = mean of the 28 days ending 28 days before d
    window = fdf[(fdf["date"] > d - pd.Timedelta(days=56))
                 & (fdf["date"] <= d - pd.Timedelta(days=28))]
    assert fdf.loc[fdf["date"] == d, "rmean_28_lag28"].iloc[0] == pytest.approx(
        window["sales"].mean())


def test_no_leakage_from_holdout_spike():
    """A spike confined to the holdout must not appear in any holdout feature."""
    df, cal, inv = make_inputs(spike_in_holdout=True)
    fdf, cols = build_features(df, cal, inv)
    _, _, holdout = temporal_split(fdf)
    lag_like = [c for c in cols if c.startswith(("lag_", "rmean_"))]
    assert holdout[lag_like].to_numpy().max() <= 10.0  # the pre-spike level


def test_cold_start_rows_are_kept_with_nan_features():
    df, cal, inv = make_inputs()
    fdf, _ = build_features(df, cal, inv)
    early = fdf[fdf["date"] < fdf["date"].min() + pd.Timedelta(days=28)]
    assert early["lag_28"].isna().all()  # no history 28 days back
    assert len(early) > 0  # rows retained, not dropped


def test_split_sizes_sum_and_holdout_is_28_days():
    df, cal, inv = make_inputs()
    fdf, _ = build_features(df, cal, inv)
    tr, va, ho = temporal_split(fdf)
    assert len(tr) + len(va) + len(ho) == len(fdf)
    assert ho["date"].nunique() == 28
    assert va["date"].nunique() == 28
    assert tr["date"].max() < va["date"].min() < ho["date"].min()
