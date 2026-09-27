"""What-if simulator tests: separation guarantees, lever math, refusal rules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from demandops import recommendations as rec
from demandops.simulator import apply_scenario, _validate_scenario


def make_risk_table() -> pd.DataFrame:
    return pd.DataFrame([
        {"unique_id": 1, "name": "A", "warehouse": "W_1", "risk_tier": "HIGH",
         "forecast_units": 500.0, "recent_availability": 0.6,
         "assumed_future_availability": 0.6,
         "estimated_unmet_units": 200.0, "risk_fraction": 0.4,
         "availability_data_gap": False},
        {"unique_id": 2, "name": "B", "warehouse": "W_2", "risk_tier": "LOW",
         "forecast_units": 100.0, "recent_availability": 1.0,
         "assumed_future_availability": 1.0,
         "estimated_unmet_units": 0.0, "risk_fraction": 0.0,
         "availability_data_gap": False},
        {"unique_id": 3, "name": "C", "warehouse": "W_1", "risk_tier": "LOW",
         "forecast_units": 80.0, "recent_availability": np.nan,
         "assumed_future_availability": np.nan,
         "estimated_unmet_units": 0.0, "risk_fraction": 0.0,
         "availability_data_gap": True},
    ])


# ---------- lever math ----------

def test_demand_multiplier_scales_demand_and_unmet():
    out = apply_scenario(make_risk_table(), demand_multiplier=1.2)
    row = out.iloc[0]
    assert row["scenario_demand_units"] == pytest.approx(600.0)
    assert row["scenario_unmet_units"] == pytest.approx(600.0 * 0.4, rel=1e-6)


def test_availability_improvement_reduces_unmet_and_caps_at_one():
    out = apply_scenario(make_risk_table(), availability_improvement=0.2)
    assert out.iloc[0]["scenario_availability"] == pytest.approx(0.8)
    assert out.iloc[0]["scenario_unmet_units"] == pytest.approx(100.0)
    # improvement beyond 1.0 saturates: unmet cannot go negative
    out2 = apply_scenario(make_risk_table(), availability_improvement=0.9)
    assert out2.iloc[0]["scenario_unmet_units"] == pytest.approx(0.0)
    assert (out2["scenario_unmet_units"] >= 0).all()


def test_promotion_uplift_uses_assumed_elasticity():
    out = apply_scenario(make_risk_table(), promo_uplift=0.356)
    assert out.iloc[0]["scenario_demand_units"] == pytest.approx(500.0 * 1.356)


def test_levers_compose_documented_way():
    out = apply_scenario(make_risk_table(), demand_multiplier=2.0,
                         promo_uplift=0.5, availability_improvement=0.1)
    row = out.iloc[0]
    assert row["scenario_demand_units"] == pytest.approx(500.0 * 2.0 * 1.5)
    assert row["scenario_availability"] == pytest.approx(0.7)
    assert row["scenario_unmet_units"] == pytest.approx(1500.0 * 0.3, rel=1e-6)


def test_identity_scenario_reproduces_baseline_exactly():
    out = apply_scenario(make_risk_table())
    assert (out["scenario_unmet_units"] - out["baseline_unmet_units"]).abs().max() < 0.01
    # data-gap row: assumed fully available, still zero unmet
    assert out.iloc[2]["scenario_unmet_units"] == 0.0


# ---------- separation guarantees ----------

def test_baseline_columns_are_never_mutated():
    risk = make_risk_table()
    original = risk.copy(deep=True)
    out = apply_scenario(risk, demand_multiplier=3.0,
                         availability_improvement=0.5)
    # input frame untouched
    pd.testing.assert_frame_equal(risk, original)
    # baseline echo columns identical to inputs
    assert (out["baseline_unmet_units"] == original["estimated_unmet_units"]).all()


def test_zero_demand_scenario_zeroes_unmet():
    out = apply_scenario(make_risk_table(), demand_multiplier=0.0)
    assert (out["scenario_unmet_units"] == 0.0).all()
    assert (out["scenario_recommended_units"] == 0).all()


# ---------- refusal of invalid scenarios ----------

@pytest.mark.parametrize("kwargs", [
    {"demand_multiplier": -0.5},
    {"promo_uplift": -0.1},
    {"availability_improvement": 1.5},
    {"availability_improvement": -0.2},
])
def test_invalid_scenario_parameters_are_refused(kwargs):
    params = {"demand_multiplier": 1.0, "promo_uplift": 0.0,
              "availability_improvement": 0.0}
    params.update(kwargs)
    with pytest.raises(ValueError):
        _validate_scenario(**params)


# ---------- consistency with the recommendation engine ----------

def test_scenario_quantity_formula_matches_recommendation_engine():
    out = apply_scenario(make_risk_table(), demand_multiplier=1.0,
                         availability_improvement=0.0)
    row = out.iloc[0]
    expected = rec.recommended_quantity(row["scenario_unmet_units"])
    assert row["scenario_recommended_units"] == expected


def test_simulator_is_deterministic():
    r = make_risk_table()
    a = apply_scenario(r, 1.5, 0.2, 0.1)
    b = apply_scenario(r.copy(), 1.5, 0.2, 0.1)
    pd.testing.assert_frame_equal(a, b)
