"""Dashboard generation tests: the decision layer must always render."""

from __future__ import annotations

import pytest

from demandops.dashboard import OUT_PATH, generate

if not (OUT_PATH.parent.parent.parent / "risk" / "risk_scores.csv").exists() and \
        not OUT_PATH.exists():
    pytest.skip("risk artifact missing — run the pipeline first",
                allow_module_level=True)


def test_dashboard_generates_and_contains_decision_content():
    out = generate()
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "Forecast quality" in html
    assert "Stockout risk tiers" in html
    assert "Recommended actions" in html
    assert "xgboost_hist_cuda" in html
    # every risk tier is represented
    for tier in ("HIGH", "MEDIUM", "LOW"):
        assert tier in html


def test_dashboard_is_selfcontained_no_external_assets():
    html = generate().read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html
    assert "<script src" not in html
