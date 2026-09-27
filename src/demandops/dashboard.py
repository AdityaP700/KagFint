"""Stakeholder dashboard (Layer 8, decision view).

Generates a self-contained static HTML page from the frozen pipeline
artifacts — no build tooling, no server required (open the file directly, or
serve via the API at /dashboard). Charts are pure CSS; no external assets,
so the file works offline and never breaks because a CDN moved.

This is deliberately NOT Streamlit/React: the decision layer here is a static
snapshot of validated artifacts. Interactive what-if analysis lives in the
API (/simulation, /docs) and the CLI. An Evidence.dev project (markdown+SQL
over the `bi` Postgres schema) is scaffolded in dashboard/ as the future BI
path; see dashboard/README.md for status.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from demandops import config

OUT_PATH = config.PROCESSED_DATA_DIR / "dashboard" / "index.html"

_CSS = """
body{font-family:'Segoe UI',system-ui,sans-serif;margin:0;background:#f4f6f8;color:#1c2733}
header{background:#12283f;color:#fff;padding:24px 36px}
header h1{margin:0;font-size:22px} header p{margin:4px 0 0;color:#9fb3c8;font-size:13px}
main{padding:24px 36px;max-width:1100px;margin:auto}
.kpis{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}
.kpi{flex:1;min-width:180px;background:#fff;border-radius:10px;padding:18px 20px;
     box-shadow:0 1px 3px rgba(16,24,40,.08)}
.kpi .v{font-size:26px;font-weight:700}.kpi .l{font-size:12px;color:#66758a;margin-top:4px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:#5a6b7f;
   border-bottom:2px solid #e3e9ef;padding-bottom:6px;margin-top:34px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
      overflow:hidden;box-shadow:0 1px 3px rgba(16,24,40,.08);font-size:13px}
th{background:#eef2f6;text-align:left;padding:9px 12px;font-size:12px;color:#415062}
td{padding:8px 12px;border-top:1px solid #eef2f6}
.badge{padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600}
.HIGH{background:#fde3e1;color:#b3261e}.MEDIUM{background:#fdf0d5;color:#8a6d00}
.LOW{background:#e1f2e6;color:#1e7b34}
.bar{background:#2e6fb7;height:14px;border-radius:3px;min-width:2px}
.bar.green{background:#2f9e5b}
.note{font-size:12px;color:#66758a;margin-top:8px}
"""


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def _bar(value: float, max_value: float, cls: str = "") -> str:
    pct = 100.0 * value / max_value if max_value else 0
    return f'<div class="bar {cls}" style="width:{pct:.1f}%"></div>'


def _load() -> dict:
    def _json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    baseline = _json(config.EXPERIMENTS_DIR / "baseline_results.json")
    gbm = _json(config.EXPERIMENTS_DIR / "gbm_results.json")
    risk = pd.read_csv(config.PROCESSED_DATA_DIR / "risk" / "risk_scores.csv")
    recs = pd.read_csv(
        config.PROCESSED_DATA_DIR / "recommendations" / "recommendations.csv")
    sims = sorted((config.PROCESSED_DATA_DIR / "simulations").glob("simulation_*.csv"))
    sim_summary = _json(sims[-1].with_name(
        sims[-1].name.replace("simulation_", "simulation_").replace(
            ".csv", "_summary.json"))) if sims else {}
    return {"baseline": baseline, "gbm": gbm, "risk": risk,
            "recs": recs, "sim": sim_summary}


def generate(out_path: Path = OUT_PATH) -> Path:
    d = _load()
    risk, recs, gbm, baseline, sim = (
        d["risk"], d["recs"], d["gbm"], d["baseline"], d["sim"])
    tiers = risk["risk_tier"].value_counts().to_dict()
    actions = recs["action"].value_counts().to_dict()
    total_unmet = risk["estimated_unmet_units"].sum()
    total_forecast = risk["forecast_units"].sum()

    gbm_o = gbm.get("results", {}).get("overall", {})
    baselines = baseline.get("results", {})

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>DemandOps — Decision Dashboard</title>",
        f"<style>{_CSS}</style></head><body>",
        "<header><h1>DemandOps — Demand &amp; Inventory Decision Dashboard</h1>",
        f"<p>Rohlik dataset · 28-day horizon · generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · all figures from pipeline-validated artifacts</p></header><main>",
    ]

    parts.append("<div class='kpis'>")
    parts.append(f"<div class='kpi'><div class='v'>{gbm_o.get('wmape', float('nan')):.1%}</div>"
                 "<div class='l'>Forecast error (WMAPE, XGBoost GPU)</div></div>")
    parts.append(f"<div class='kpi'><div class='v'>{_fmt(total_forecast)}</div>"
                 "<div class='l'>Forecast units, next 28 days</div></div>")
    parts.append(f"<div class='kpi'><div class='v'>{_fmt(total_unmet)}</div>"
                 "<div class='l'>Units at risk (availability-adjusted)</div></div>")
    parts.append(f"<div class='kpi'><div class='v'>{tiers.get('HIGH', 0):,}</div>"
                 "<div class='l'>HIGH-risk product-warehouses</div></div>")
    parts.append("</div>")

    # Forecast quality vs baselines.
    parts.append("<h2>Forecast quality (temporal holdout)</h2><table>"
                 "<tr><th>Model</th><th>WMAPE</th><th>Weighted WMAPE</th><th>MAE</th></tr>")
    for name, r in baselines.items():
        o = r["overall"]
        parts.append(f"<tr><td>{name}</td><td>{o['wmape']:.1%}</td>"
                     f"<td>{o['wmape_weighted']:.1%}</td><td>{o['mae']:.2f}</td></tr>")
    if gbm_o:
        parts.append(f"<tr><td><b>xgboost_hist_cuda (GPU)</b></td>"
                     f"<td><b>{gbm_o['wmape']:.1%}</b></td>"
                     f"<td><b>{gbm_o['wmape_weighted']:.1%}</b></td>"
                     f"<td><b>{gbm_o['mae']:.2f}</b></td></tr>")
    parts.append("</table><div class='note'>Chronological split: models train on the "
                 "past, score on the final 28 days. Weighted = competition WMAPE weights.</div>")

    # Risk tiers with CSS bars.
    parts.append("<h2>Stockout risk tiers</h2><table>")
    max_tier = max(tiers.values()) if tiers else 1
    for tier in ("HIGH", "MEDIUM", "LOW"):
        parts.append(f"<tr><td><span class='badge {tier}'>{tier}</span></td>"
                     f"<td>{tiers.get(tier, 0):,}</td>"
                     f"<td style='width:50%'>{_bar(tiers.get(tier, 0), max_tier)}</td></tr>")
    parts.append("</table><div class='note'>OBSERVED availability · DERIVED forecasts · "
                 "ASSUMED future availability = recent availability.</div>")

    # Top high-risk table.
    parts.append("<h2>Top HIGH-risk products</h2><table><tr><th>Product</th>"
                 "<th>Warehouse</th><th>Forecast units (28d)</th><th>Observed availability</th>"
                 "<th>Units at risk</th></tr>")
    top = risk[risk["risk_tier"] == "HIGH"].head(10)
    for _, r in top.iterrows():
        parts.append(f"<tr><td>{r['name']}</td><td>{r['warehouse']}</td>"
                     f"<td>{r['forecast_units']:,.0f}</td>"
                     f"<td>{r['recent_availability']:.0%}</td>"
                     f"<td>{r['estimated_unmet_units']:,.0f}</td></tr>")
    parts.append("</table>")

    # Recommended actions.
    parts.append("<h2>Recommended actions</h2><table>")
    for action, count in sorted(actions.items(), key=lambda kv: -kv[1]):
        parts.append(f"<tr><td>{action}</td><td>{count:,} series</td></tr>")
    parts.append("</table><div class='note'>Versioned engine output; quantities include a "
                 "labeled +10% safety margin. Data-gap series get a data-fix action, "
                 "not a stock order.</div>")

    # What-if scenario.
    if sim:
        parts.append("<h2>Latest what-if scenario</h2><table>"
                     "<tr><th>Scenario</th><th>Baseline unmet</th><th>Scenario unmet</th>"
                     "<th>Delta</th></tr>")
        sc = sim.get("scenario", {})
        label = (f"demand ×{sc.get('demand_multiplier', 1):g}, "
                 f"promos +{sc.get('promotion_uplift', 0):.0%}, "
                 f"availability +{sc.get('availability_improvement', 0):g}")
        parts.append(f"<tr><td>{label}</td>"
                     f"<td>{sim['total_baseline_unmet_units']:,.0f}</td>"
                     f"<td>{sim['total_scenario_unmet_units']:,.0f}</td>"
                     f"<td>{sim['unmet_units_delta']:+,.0f}</td></tr></table>")
    parts.append("</main></body></html>")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def main() -> int:
    out = generate()
    print(f"dashboard written: {out.relative_to(config.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
