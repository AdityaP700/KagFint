"""Tests for metrics and baseline forecasters on small synthetic series."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from demandops import metrics
from demandops.baselines import moving_average, seasonal_naive


# ---------- metrics ----------

def test_mae_rmse_basic():
    y = np.array([1.0, 2.0, 3.0])
    yhat = np.array([1.0, 2.0, 5.0])
    assert metrics.mae(y, yhat) == pytest.approx(2 / 3)
    assert metrics.rmse(y, yhat) == pytest.approx(np.sqrt((0 + 0 + 4) / 3))


def test_wmape_unweighted():
    y = np.array([10.0, 10.0])
    yhat = np.array([9.0, 11.0])
    assert metrics.wmape(y, yhat) == pytest.approx(2 / 20)


def test_wmape_weighted_stresses_important_series():
    y = np.array([100.0, 1.0])
    yhat = np.array([110.0, 2.0])  # off by 10% and 100% respectively
    w = np.array([10.0, 1.0])
    # sum(w*|err|) / sum(w*|y|) = (10*10 + 1*1) / (10*100 + 1*1)
    assert metrics.wmape(y, yhat, w) == pytest.approx(101 / 1001)


def test_metrics_ignore_null_pairs_but_shapes_must_match():
    y = np.array([1.0, np.nan, 3.0])
    yhat = np.array([2.0, 2.0, 3.0])
    assert metrics.mae(y, yhat) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        metrics.mae(np.array([1.0, 2.0]), np.array([1.0]))


def test_wmape_all_zero_actuals_is_nan_not_fake_zero():
    assert np.isnan(metrics.wmape(np.zeros(3), np.ones(3)))


# ---------- baselines ----------

def make_history(weeks: int = 8, base: float = 10.0) -> pd.DataFrame:
    # Daily series with a strong weekly pattern: weekends double.
    dates = pd.date_range("2024-01-01", periods=weeks * 7)
    sales = [base * (2 if d.dayofweek >= 5 else 1) for d in dates]
    return pd.DataFrame({"unique_id": 1, "date": dates, "sales": sales})


def test_seasonal_naive_tiles_last_week():
    history = make_history()
    horizon = pd.date_range("2024-02-26", periods=7)  # the week after history ends
    preds = seasonal_naive(history, list(horizon))
    assert len(preds) == 7
    # The last history week ended 2024-02-25 (a Sunday); the pattern must repeat.
    joined = preds.set_index("date")["prediction"]
    sat = [d for d in horizon if d.dayofweek == 5][0]
    assert joined[sat] == pytest.approx(20.0)  # weekend value
    mon = [d for d in horizon if d.dayofweek == 0][0]
    assert joined[mon] == pytest.approx(10.0)


def test_moving_average_flat_and_correct():
    history = make_history()
    horizon = pd.date_range("2024-02-26", periods=7)
    preds = moving_average(history, list(horizon), window=28)
    expected = history["sales"].tail(28).mean()
    assert preds["prediction"].nunique() == 1
    assert preds["prediction"].iloc[0] == pytest.approx(expected)


def test_baselines_cover_every_series_and_date():
    history = make_history()
    history2 = history.assign(unique_id=2)
    history = pd.concat([history, history2])
    horizon = list(pd.date_range("2024-02-26", periods=14))
    preds = seasonal_naive(history, horizon)
    assert len(preds) == 2 * len(horizon)
    assert not preds["prediction"].isna().any()


def test_null_sales_are_filled_not_propagated():
    history = make_history(weeks=2)
    history.loc[history.index[-1], "sales"] = np.nan  # a documented raw null
    horizon = pd.date_range("2024-01-15", periods=7)
    preds = seasonal_naive(history, list(horizon))
    assert not preds["prediction"].isna().any()


def test_regularize_repair_gap_in_middle_of_series():
    # Regression test: reindexing over gap days must keep the series id on
    # every row (a NaN-id grid once corrupted pattern extraction on real data).
    history = pd.DataFrame({
        "unique_id": 1,
        "date": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-05")],
        "sales": [5.0, 15.0],
    })
    horizon = pd.date_range("2024-01-06", periods=7)
    preds = seasonal_naive(history, list(horizon))
    assert len(preds) == 7
    assert not preds["prediction"].isna().any()
    # Sat/Sun (no pattern, not cold-start-short) -> mean fallback (7.0);
    # Mon..Thu -> pattern 5.0; Fri -> pattern 15.0.
    by_date = preds.set_index("date")["prediction"]
    assert by_date[pd.Timestamp("2024-01-12")] == pytest.approx(15.0)
    assert by_date[pd.Timestamp("2024-01-06")] == pytest.approx(7.0)
    assert preds.attrs["fallback_series"] == 1


def test_cold_start_series_use_documented_fallback():
    # A series with only 3 days of history has no weekly pattern; its missing
    # weekdays fall back to the mean of its available days.
    short = pd.DataFrame({
        "unique_id": 9,
        "date": pd.date_range("2024-02-23", periods=3),  # Fri, Sat, Sun
        "sales": [5.0, 10.0, 15.0],
    })
    history = pd.concat([make_history(), short])
    horizon = pd.date_range("2024-02-26", periods=7)  # Mon..Sun after history
    preds = seasonal_naive(history, list(horizon))
    assert not preds["prediction"].isna().any()
    assert preds.attrs["fallback_series"] == 1
    mon = preds[preds["date"] == pd.Timestamp("2024-02-26")]
    assert mon["prediction"].iloc[0] == pytest.approx(10.0)  # mean(5,10,15)


def test_empty_history_rejected():
    with pytest.raises(ValueError):
        seasonal_naive(pd.DataFrame(columns=["unique_id", "date", "sales"]),
                       [pd.Timestamp("2024-01-01")])
