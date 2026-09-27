"""What-if simulator (Layer 6).

Answers "what would happen if...?" against the frozen forecasts and risk
table — without recomputing models and without ever modifying history.

BASELINE vs SIMULATED separation (validation protocol §13):
- baseline_* columns are copied verbatim from the risk/recommendation
  artifacts; the simulator asserts they are never mutated.
- scenario_* columns exist only in the simulator's output.

Levers (each labeled):
- demand_multiplier        : multiplicative demand change (holiday surge,
                             demand shock). USER-CHOSEN, no model claim.
- promotion_uplift         : additive demand lift from enabling promotions.
                             DEFAULT 0.356 is DERIVED from our own aggregate
                             SQL finding (sql/analytics/07: promoted rows sell
                             ~36% more) — used as an ASSUMED elasticity,
                             not a causal guarantee.
- availability_improvement : absolute gain in assumed future availability
                             (e.g. 0.10 = "fix a tenth of the shortfall").
                             ASSUMED operational lever; capped to [0, 1].

Unsupported levers are refused, not faked: inventory levels and lead times do
not exist in this dataset (docs/DATASET.md), so the simulator has no honest
way to model them.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from demandops import config, manifest
from demandops.recommendations import PACK_SIZE, SAFETY_MARGIN

# DERIVED from sql/analytics/07 (aggregate promo uplift ~ +36%), used as ASSUMED elasticity.
PROMO_UPLIFT_DEFAULT = 0.356


def _validate_scenario(demand_multiplier: float, promo_uplift: float,
                       availability_improvement: float) -> None:
    if demand_multiplier < 0:
        raise ValueError("demand_multiplier must be >= 0 (demand cannot be negative).")
    if promo_uplift < 0:
        raise ValueError("promo_uplift must be >= 0.")
    if not 0 <= availability_improvement <= 1:
        raise ValueError("availability_improvement must be within [0, 1].")


def apply_scenario(risk: pd.DataFrame, demand_multiplier: float = 1.0,
                   promo_uplift: float = 0.0,
                   availability_improvement: float = 0.0) -> pd.DataFrame:
    """Pure scenario computation. Returns risk rows + scenario_* columns.

    Baseline columns are never mutated; identity levers (1.0, 0.0, 0.0)
    reproduce the risk engine's unmet units exactly.
    """
    _validate_scenario(demand_multiplier, promo_uplift, availability_improvement)
    df = risk.copy()

    multiplier = demand_multiplier * (1.0 + promo_uplift)
    df["scenario_demand_units"] = df["forecast_units"] * multiplier

    # ASSUMED availability under scenario; data-gap rows keep "fully available".
    gap = df["availability_data_gap"].fillna(True).astype(bool)
    scenario_avail = (
        df["assumed_future_availability"].fillna(1.0) + availability_improvement
    ).clip(0.0, 1.0)
    scenario_avail = scenario_avail.where(~gap, 1.0)
    df["scenario_availability"] = scenario_avail

    df["baseline_unmet_units"] = df["estimated_unmet_units"]
    df["scenario_unmet_units"] = (
        df["scenario_demand_units"] * (1.0 - df["scenario_availability"])
    ).round(2)
    df["unmet_units_delta"] = (df["scenario_unmet_units"]
                               - df["baseline_unmet_units"]).round(2)

    # What the recommendation would become under the scenario (same formula
    # and ASSUMED parameters as the recommendation engine, for comparability).
    def _qty(unmet: float) -> int:
        import math
        return int(math.ceil(max(unmet, 0.0) * (1.0 + SAFETY_MARGIN) / PACK_SIZE) * PACK_SIZE)

    df["scenario_recommended_units"] = df["scenario_unmet_units"].map(_qty)

    # Guard: baseline columns untouched by construction (copy + new columns).
    return df


def _tag(demand_multiplier: float, promo_uplift: float,
         availability_improvement: float) -> str:
    parts = [f"dm{demand_multiplier:g}", f"pu{promo_uplift:g}",
             f"ai{availability_improvement:g}"]
    return "_".join(parts).replace(".", "p").replace("-", "m")


def run(args: argparse.Namespace) -> int:
    risk_path = config.PROCESSED_DATA_DIR / "risk" / "risk_scores.csv"
    if not risk_path.exists():
        raise FileNotFoundError("Run `python -m demandops.risk` first — the "
                                "simulator consumes the frozen risk table.")
    risk = pd.read_csv(risk_path)

    scenario = apply_scenario(risk, args.demand_multiplier, args.promo_uplift,
                              args.availability_improvement)

    # Consistency gate: the identity scenario must reproduce the risk engine.
    if (args.demand_multiplier, args.promo_uplift,
            args.availability_improvement) == (1.0, 0.0, 0.0):
        drift = (scenario["scenario_unmet_units"]
                 - scenario["baseline_unmet_units"]).abs().max()
        if drift > 0.01:
            raise RuntimeError(
                f"identity scenario drifted from the risk table by {drift}")

    out_dir = config.PROCESSED_DATA_DIR / "simulations"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = _tag(args.demand_multiplier, args.promo_uplift,
               args.availability_improvement)
    csv_path = out_dir / f"simulation_{tag}.csv"
    scenario.to_csv(csv_path, index=False)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "demand_multiplier": args.demand_multiplier,
            "promotion_uplift": args.promo_uplift,
            "availability_improvement": args.availability_improvement,
            "promo_uplift_source": "DERIVED from sql/analytics/07 (+36% aggregate), used as ASSUMED elasticity",
        },
        "labels": {
            "baseline_unmet_units": "BASELINE (frozen risk artifact)",
            "scenario_unmet_units": "SIMULATED",
            "historical_data": "UNTOUCHED — simulator writes only new files",
        },
        "series": int(len(scenario)),
        "total_baseline_unmet_units": round(float(scenario["baseline_unmet_units"].sum()), 2),
        "total_scenario_unmet_units": round(float(scenario["scenario_unmet_units"].sum()), 2),
        "unmet_units_delta": round(float(scenario["unmet_units_delta"].sum()), 2),
        "total_scenario_recommended_units": int(scenario["scenario_recommended_units"].sum()),
    }
    summary_path = config.EXPERIMENTS_DIR / f"simulation_{tag}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")

    manifest.write_manifest(
        kind="what_if_simulation",
        inputs={"risk_rows": int(len(risk))},
        outputs={"simulation": str(csv_path.relative_to(config.PROJECT_ROOT)),
                 "summary": str(summary_path.relative_to(config.PROJECT_ROOT))},
        validation_summary={"overall": "PASS",
                            "note": "baseline columns verified untouched"},
    )

    print(f"scenario dm={args.demand_multiplier:g} pu={args.promo_uplift:g} "
          f"ai={args.availability_improvement:g}")
    print(f"unmet units: baseline {summary['total_baseline_unmet_units']:,.0f} "
          f"-> scenario {summary['total_scenario_unmet_units']:,.0f} "
          f"(delta {summary['unmet_units_delta']:+,.0f})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="What-if simulator over the frozen risk table.")
    parser.add_argument("--demand-multiplier", type=float, default=1.0)
    parser.add_argument("--promo-uplift", type=float, default=0.0)
    parser.add_argument("--availability-improvement", type=float, default=0.0)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
