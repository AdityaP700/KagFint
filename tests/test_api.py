"""API tests (validation protocol §12): health, valid requests, malformed
requests, invalid filters, unknown entities, and the error contract.

Runs against the real pipeline artifacts in data/processed/ — if they are
missing, tests skip with a pointer to the pipeline command.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from demandops.api import ARTIFACTS, app

if not ARTIFACTS["risk"].exists():
    pytest.skip("risk artifact missing — run `python -m demandops.risk` first",
                allow_module_level=True)


@pytest.fixture(scope="module")
def client():
    # Lifespan (artifact loading) only runs inside the context manager.
    with TestClient(app) as c:
        yield c


# ---------- health ----------

def test_health_reports_artifact_status(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["artifacts"]["risk"] is True


# ---------- forecast endpoints ----------

def test_forecast_summary_contains_model_and_baselines(client):
    r = client.get("/forecast/summary")
    assert r.status_code == 200
    body = r.json()
    assert "gbm" in body and "baselines" in body
    assert 0 < body["gbm"]["wmape"] < 1


def test_forecast_series_valid_and_unknown_entity(client):
    assert client.get("/forecast/series/1").status_code == 200
    r = client.get("/forecast/series/1")
    assert r.json()[0]["prediction"] >= 0
    assert client.get("/forecast/series/999999999").status_code == 404
    # malformed: non-integer path parameter
    assert client.get("/forecast/series/not-an-int").status_code == 422


# ---------- risk endpoints ----------

def test_risk_default_limit_respected(client):
    r = client.get("/risk", params={"limit": 10})
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_risk_tier_filter_returns_only_that_tier(client):
    r = client.get("/risk", params={"tier": "HIGH", "limit": 100})
    assert r.status_code == 200
    assert {row["risk_tier"] for row in r.json()} == {"HIGH"}


def test_risk_invalid_tier_is_rejected_not_accepted(client):
    assert client.get("/risk", params={"tier": "WHATEVER"}).status_code == 422


def test_risk_limit_bounds_enforced(client):
    assert client.get("/risk", params={"limit": 0}).status_code == 422
    assert client.get("/risk", params={"limit": 10_000}).status_code == 422


def test_risk_summary_tier_counts_consistent(client):
    r = client.get("/risk/summary")
    assert r.status_code == 200
    counts = r.json()["tier_counts"]
    assert counts.get("HIGH", 0) > 0


# ---------- recommendations ----------

def test_recommendations_action_filter(client):
    r = client.get("/recommendations", params={"action": "replenish_now",
                                               "limit": 25})
    assert r.status_code == 200
    rows = r.json()
    assert 0 < len(rows) <= 25
    assert {row["action"] for row in rows} == {"replenish_now"}


def test_recommendations_invalid_action_rejected(client):
    assert client.get("/recommendations",
                      params={"action": "do_everything"}).status_code == 422


def test_recommendations_well_formed_request_returns_rows(client):
    r = client.get("/recommendations", params={"limit": 1})
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---------- simulation ----------

def test_simulation_valid_scenario_returns_deltas(client):
    r = client.post("/simulation", json={
        "demand_multiplier": 1.2, "promotion_uplift": 0.1,
        "availability_improvement": 0.05})
    assert r.status_code == 200
    body = r.json()
    assert body["series"] > 0
    assert "unmet_units_delta" in body


def test_simulation_identity_matches_baseline_within_tolerance(client):
    r = client.post("/simulation", json={})
    assert r.status_code == 200
    assert abs(r.json()["unmet_units_delta"]) < 1.0


def test_simulation_out_of_range_parameters_rejected(client):
    assert client.post("/simulation",
                       json={"demand_multiplier": -1}).status_code == 422
    assert client.post("/simulation",
                       json={"availability_improvement": 1.5}).status_code == 422


# ---------- interactive docs ----------

def test_openapi_docs_are_exposed(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/risk" in r.json()["paths"]
