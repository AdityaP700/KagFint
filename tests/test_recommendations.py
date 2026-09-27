"""Recommendation-engine tests: contracts, invariants, boundaries, degradation.

The goal is breadth: input-contract failures, quantity properties across many
inputs, tier-boundary mappings, data-gap degradation, determinism, and the
shape of the output itself (production-minded contract testing).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from demandops import recommendations as rec
from demandops.recommendations import (
    ENGINE_VERSION, PACK_SIZE, REQUIRED_RISK_COLUMNS, SAFETY_MARGIN,
    generate_recommendations, recommended_quantity, _validate_input,
)


def make_risk_row(**overrides) -> dict:
    base = {
        "unique_id": 1, "name": "Berry_1", "warehouse": "Prague_1",
        "risk_tier": "HIGH",
        "forecast_units": 500.0, "recent_availability": 0.6,
        "assumed_future_availability": 0.6,
        "estimated_unmet_units": 200.0, "risk_fraction": 0.4,
        "availability_data_gap": False,
    }
    base.update(overrides)
    return base


def make_risk_table(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ---------- input contract ----------

def test_missing_required_column_raises_contract_error():
    table = make_risk_table([make_risk_row()]).drop(columns=["risk_fraction"])
    with pytest.raises(ValueError, match="input contract"):
        generate_recommendations(table)


def test_empty_contract_violation_lists_all_missing_columns():
    with pytest.raises(ValueError) as exc:
        _validate_input(pd.DataFrame())
    for col in REQUIRED_RISK_COLUMNS:
        assert col in str(exc.value)


# ---------- quantity formula: properties across many inputs ----------

@pytest.mark.parametrize("unmet", [0.0, 1.0, 4.9, 5.0, 17.3, 199.9, 10_000.0, 123_456.7])
def test_quantity_never_under_covers(unmet: float):
    qty = recommended_quantity(unmet)
    assert qty >= unmet * (1 + SAFETY_MARGIN) - 1e-9


@pytest.mark.parametrize("unmet", [1.0, 5.0, 17.3, 199.9, 10_000.0])
def test_quantity_over_cover_is_bounded(unmet: float):
    qty = recommended_quantity(unmet)
    # at most margin plus one extra pack
    assert qty <= unmet * (1 + SAFETY_MARGIN) + PACK_SIZE + 1e-9


@pytest.mark.parametrize("unmet", [1.0, 17.3, 123_456.7])
def test_quantity_is_a_pack_multiple(unmet: float):
    assert recommended_quantity(unmet) % PACK_SIZE == 0


def test_zero_unmet_recommends_zero_units():
    assert recommended_quantity(0.0) == 0


def test_negative_unmet_is_clamped_not_propagated():
    assert recommended_quantity(-50.0) == 0


# ---------- action mapping and boundaries ----------

def test_high_medium_low_map_to_their_actions():
    table = make_risk_table([
        make_risk_row(unique_id=1, risk_tier="HIGH"),
        make_risk_row(unique_id=2, risk_tier="MEDIUM"),
        make_risk_row(unique_id=3, risk_tier="LOW"),
    ])
    by_id = generate_recommendations(table).set_index("unique_id")
    assert by_id.loc[1, "action"] == "replenish_now"
    assert by_id.loc[2, "action"] == "replenish_scheduled"
    assert by_id.loc[3, "action"] == "monitor"
    assert by_id.loc[3, "recommended_units"] == 0


def test_data_gap_degrades_to_investigate_not_replenish():
    table = make_risk_table([make_risk_row(availability_data_gap=True)])
    row = generate_recommendations(table).iloc[0]
    assert row["action"] == "investigate_data"
    assert row["recommended_units"] == 0
    assert "data feed" in row["rationale"]


def test_nan_availability_treated_as_data_gap():
    table = make_risk_table([make_risk_row(assumed_future_availability=np.nan)])
    row = generate_recommendations(table).iloc[0]
    assert row["action"] == "investigate_data"


def test_unknown_tier_degrades_to_monitor_not_crash():
    table = make_risk_table([make_risk_row(risk_tier="EXTREME")])
    row = generate_recommendations(table).iloc[0]
    assert row["action"] == "monitor"
    assert row["rule_id"] == "R0_unknown_tier"


def test_extreme_demand_spike_passes_through_deterministically():
    table = make_risk_table([make_risk_row(estimated_unmet_units=1e6,
                                           forecast_units=2e6)])
    qty = generate_recommendations(table).iloc[0]["recommended_units"]
    assert qty >= 1e6
    assert qty == recommended_quantity(1e6)


# ---------- output shape / auditability contract ----------

def test_every_row_has_valid_action_rule_id_and_version():
    table = make_risk_table([
        make_risk_row(unique_id=i, risk_tier=t, availability_data_gap=g)
        for i, (t, g) in enumerate(
            [("HIGH", False), ("MEDIUM", False), ("LOW", False), ("HIGH", True)])
    ])
    out = generate_recommendations(table)
    assert set(out["action"]).issubset(rec.VALID_ACTIONS)
    assert out["rule_id"].notna().all()
    assert (out["engine_version"] == ENGINE_VERSION).all()


def test_rationale_contains_the_actual_numbers():
    table = make_risk_table([make_risk_row(forecast_units=500.0,
                                           estimated_unmet_units=200.0)])
    text = generate_recommendations(table).iloc[0]["rationale"]
    assert "500" in text and "200" in text and "60%" in text


def test_assumptions_are_labeled_not_hidden():
    table = make_risk_table([make_risk_row()])
    assumptions = generate_recommendations(table).iloc[0]["assumptions"]
    assert "ASSUMED" in assumptions


def test_recommendations_sorted_by_priority_then_unmet():
    table = make_risk_table([
        make_risk_row(unique_id=1, risk_tier="LOW", estimated_unmet_units=0.0),
        make_risk_row(unique_id=2, risk_tier="MEDIUM", estimated_unmet_units=50.0),
        make_risk_row(unique_id=3, risk_tier="HIGH", estimated_unmet_units=20.0),
        make_risk_row(unique_id=4, risk_tier="HIGH", estimated_unmet_units=300.0),
    ])
    out = generate_recommendations(table)
    assert list(out["unique_id"]) == [4, 3, 2, 1]


# ---------- determinism ----------

def test_engine_is_deterministic():
    table = make_risk_table([make_risk_row(unique_id=i) for i in range(5)])
    pd.testing.assert_frame_equal(generate_recommendations(table),
                                  generate_recommendations(table.copy()))
