"""Tests for the deterministic stockout risk engine (boundary cases included)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from demandops.risk import compute_risk


def make_forecasts(units_by_series: dict[int, float]) -> pd.DataFrame:
    rows = []
    for uid, total in units_by_series.items():
        per_day = total / 28
        for d in range(28):
            rows.append({"unique_id": uid, "date": pd.Timestamp("2024-05-06") + pd.Timedelta(days=d),
                         "prediction": per_day})
    return pd.DataFrame(rows)


def make_availability(avail_by_series: dict[int, float | None]) -> pd.DataFrame:
    rows = []
    for uid, av in avail_by_series.items():
        rows.append({"unique_id": uid, "recent_availability": av,
                     "n_days_observed": 28 if av is not None else 0,
                     "low_avail_days": 0 if av is None or av >= 0.5 else 10})
    return pd.DataFrame(rows)


def test_zero_availability_high_demand_is_high_risk():
    risk = compute_risk(make_forecasts({1: 280.0}),
                        make_availability({1: 0.0}))
    row = risk.iloc[0]
    assert row["risk_tier"] == "HIGH"
    assert row["estimated_unmet_units"] == pytest.approx(280.0)
    assert row["risk_fraction"] == pytest.approx(1.0)


def test_full_availability_is_low_risk_with_zero_unmet():
    risk = compute_risk(make_forecasts({1: 280.0}),
                        make_availability({1: 1.0}))
    row = risk.iloc[0]
    assert row["risk_tier"] == "LOW"
    assert row["estimated_unmet_units"] == 0.0


def test_zero_forecast_cannot_be_high_risk():
    risk = compute_risk(make_forecasts({1: 0.0}),
                        make_availability({1: 0.0}))
    row = risk.iloc[0]
    assert row["risk_tier"] == "LOW"
    assert row["risk_fraction"] == 0.0  # no division blow-ups


def test_tier_threshold_boundaries():
    # unmet 10 units of 200 -> fraction exactly 0.05: MEDIUM boundary
    # (unmet >= 5 AND fraction >= 0.05, but below HIGH's requirements)
    risk = compute_risk(make_forecasts({1: 200.0}),
                        make_availability({1: 0.95}))
    assert risk.iloc[0]["risk_tier"] == "MEDIUM"
    # unmet exactly 28 units of 280 -> fraction 0.10 AND unmet >= 10: HIGH
    risk = compute_risk(make_forecasts({1: 280.0}),
                        make_availability({1: 0.9}))
    assert risk.iloc[0]["risk_tier"] == "HIGH"
    # unmet 10 units of 280 -> fraction 0.0357 (< 0.05): LOW despite unmet >= 5
    risk = compute_risk(make_forecasts({1: 280.0}),
                        make_availability({1: 1 - 10 / 280}))
    assert risk.iloc[0]["risk_tier"] == "LOW"


def test_missing_availability_history_flags_gap_and_assumes_available():
    risk = compute_risk(make_forecasts({1: 280.0}),
                        make_availability({1: None}))
    row = risk.iloc[0]
    assert bool(row["availability_data_gap"]) is True
    assert row["assumed_future_availability"] == 1.0
    assert row["estimated_unmet_units"] == 0.0
    assert row["risk_tier"] == "LOW"


def test_engine_is_deterministic():
    f, a = make_forecasts({1: 280.0, 2: 50.0}), make_availability({1: 0.8, 2: 0.95})
    r1 = compute_risk(f, a)
    r2 = compute_risk(f.copy(), a.copy())
    pd.testing.assert_frame_equal(r1, r2)


def test_unknown_series_in_forecasts_get_gap_treatment():
    f = make_forecasts({1: 280.0})
    f = pd.concat([f, make_forecasts({99: 140.0})], ignore_index=True)
    risk = compute_risk(f, make_availability({1: 0.8}))
    row = risk[risk["unique_id"] == 99].iloc[0]
    assert bool(row["availability_data_gap"]) is True
    assert row["risk_tier"] == "LOW"
