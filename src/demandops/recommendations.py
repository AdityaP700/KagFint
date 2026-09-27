"""Recommendation engine (Layer 5).

Converts risk rows (Checkpoint 07) into deterministic replenishment
recommendations. Production principles applied here:

- INPUT CONTRACT: required columns are validated up front; schema drift fails
  loudly instead of producing silent garbage downstream.
- VERSIONED RULES: every recommendation carries engine_version and rule_id,
  so an audited output can be traced to the exact rule set that produced it.
- DETERMINISM: same risk table -> byte-identical recommendations.
- LABELED ASSUMPTIONS: the safety margin and pack size are ASSUMED business
  parameters, carried on every row; no number is presented as authoritative.
- TOTAL COVERAGE: every input row yields exactly one valid action — unknown
  conditions degrade to a conservative action (monitor / investigate_data),
  never to silence.

Actions:
- replenish_now      (HIGH risk: unmet demand is large and imminent)
- replenish_scheduled(MEDIUM risk: cover at the next ordering cycle)
- investigate_data   (availability telemetry missing — fix the data feed
                      before spending money on stock)
- monitor            (LOW risk)

Quantity formula (ASSUMED parameters):
    recommended_units = ceil(unmet * (1 + SAFETY_MARGIN) / PACK_SIZE) * PACK_SIZE
Invariants (tested): never under-covers unmet demand; over-cover is bounded
by SAFETY_MARGIN plus one pack; zero-unmet rows recommend zero units.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from demandops import config, manifest

ENGINE_VERSION = "1.0.0"
SAFETY_MARGIN = 0.10      # ASSUMED business parameter
PACK_SIZE = 5             # ASSUMED business parameter

REQUIRED_RISK_COLUMNS = [
    "unique_id", "name", "warehouse", "risk_tier",
    "forecast_units", "recent_availability",
    "assumed_future_availability", "estimated_unmet_units",
    "risk_fraction", "availability_data_gap",
]

VALID_ACTIONS = {"replenish_now", "replenish_scheduled", "investigate_data", "monitor"}

PRIORITY = {"HIGH": 1, "MEDIUM": 2, "LOW": 4}
ACTION_FOR_TIER = {"HIGH": "replenish_now", "MEDIUM": "replenish_scheduled",
                   "LOW": "monitor"}


def _validate_input(risk: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_RISK_COLUMNS if c not in risk.columns]
    if missing:
        raise ValueError(
            f"risk table violates the input contract; missing columns: {missing}. "
            "Regenerate it with `python -m demandops.risk`.")


def _round_up_to_pack(units: float) -> int:
    return int(math.ceil(units / PACK_SIZE) * PACK_SIZE)


def recommended_quantity(unmet: float) -> int:
    """Quantity formula with invariant: never under-covers, bounded over-cover."""
    unmet = max(float(unmet), 0.0)
    if unmet == 0.0:
        return 0
    return _round_up_to_pack(unmet * (1.0 + SAFETY_MARGIN))


def _recommend_row(row: pd.Series) -> dict:
    tier = row["risk_tier"]
    unmet = max(float(row["estimated_unmet_units"]), 0.0)
    is_gap = bool(row["availability_data_gap"]) or pd.isna(
        row["assumed_future_availability"])

    if is_gap:
        action, rule_id = "investigate_data", "R4_availability_data_gap"
        qty = 0
        rationale = (
            f"Availability telemetry missing for series {int(row['unique_id'])}; "
            "no scarcity signal can be computed. Fix the data feed before "
            "committing stock decisions.")
        assumptions = ["ASSUMED: absent telemetry treated as fully available "
                       "(inherited from the risk engine)"]
    elif tier in ACTION_FOR_TIER:
        action = ACTION_FOR_TIER[tier]
        rule_id = {"HIGH": "R1_high_risk_replenish",
                   "MEDIUM": "R2_medium_risk_schedule",
                   "LOW": "R3_monitor"}[tier]
        qty = recommended_quantity(unmet) if tier != "LOW" else 0
        rationale = (
            f"Tier {tier}: forecast {row['forecast_units']:.0f} units over the "
            f"horizon at {row['recent_availability']:.0%} observed availability; "
            f"assuming future availability equals recent, ~{unmet:.0f} units "
            f"would go unmet. {cap_first(action)}: recommend {qty} units "
            f"(+{SAFETY_MARGIN:.0%} safety margin, packed in {PACK_SIZE}s).")
        assumptions = [
            f"ASSUMED: future availability = recent observed "
            f"({row['assumed_future_availability']:.0%})",
            f"ASSUMED: safety margin {SAFETY_MARGIN:.0%}, pack size {PACK_SIZE}",
        ]
    else:
        # Unknown tier values degrade conservatively instead of crashing.
        action, rule_id, qty = "monitor", "R0_unknown_tier", 0
        rationale = f"Unrecognized risk tier '{tier}'; defaulted to monitoring."
        assumptions = []

    return {
        "unique_id": row["unique_id"],
        "name": row.get("name"),
        "warehouse": row["warehouse"],
        "risk_tier": tier,
        "action": action,
        "recommended_units": qty,
        "estimated_unmet_units": unmet,
        "priority": PRIORITY.get(tier, 3 if is_gap else 4),
        "rule_id": rule_id,
        "engine_version": ENGINE_VERSION,
        "rationale": rationale,
        "assumptions": " | ".join(assumptions),
    }


def cap_first(s: str) -> str:
    return s[0].upper() + s[1:]


def generate_recommendations(risk: pd.DataFrame) -> pd.DataFrame:
    """Pure transformation: risk table -> recommendation table."""
    _validate_input(risk)
    recs = pd.DataFrame([_recommend_row(row) for _, row in risk.iterrows()])
    assert set(recs["action"]).issubset(VALID_ACTIONS)
    return recs.sort_values(
        ["priority", "estimated_unmet_units"], ascending=[True, False]
    ).reset_index(drop=True)


def run() -> int:
    risk_path = config.PROCESSED_DATA_DIR / "risk" / "risk_scores.csv"
    if not risk_path.exists():
        raise FileNotFoundError(
            "No risk table found — run `python -m demandops.risk` first. "
            "The recommendation layer consumes risk scores; it never "
            "recomputes them.")
    risk = pd.read_csv(risk_path)
    recs = generate_recommendations(risk)

    out_dir = config.PROCESSED_DATA_DIR / "recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)
    rec_path = out_dir / "recommendations.csv"
    recs.to_csv(rec_path, index=False)

    actions = recs["action"].value_counts().to_dict()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "input_rows": int(len(risk)),
        "recommendation_rows": int(len(recs)),
        "action_counts": actions,
        "assumed_parameters": {"safety_margin": SAFETY_MARGIN,
                               "pack_size": PACK_SIZE},
        "top_replenish_now": recs[recs["action"] == "replenish_now"].head(10)[
            ["name", "warehouse", "recommended_units",
             "estimated_unmet_units"]].to_dict("records"),
    }
    summary_path = config.EXPERIMENTS_DIR / "recommendations_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")

    manifest.write_manifest(
        kind="recommendations",
        inputs={"risk_rows": int(len(risk))},
        outputs={"recommendations": str(rec_path.relative_to(config.PROJECT_ROOT)),
                 "summary": str(summary_path.relative_to(config.PROJECT_ROOT))},
        validation_summary={"overall": "PASS",
                            "engine_version": ENGINE_VERSION,
                            "note": "deterministic; input contract enforced"},
    )

    print(f"recommendations ({len(recs)} rows): {actions}")
    print(f"engine {ENGINE_VERSION}; outputs -> {rec_path.name}, "
          f"summary -> {summary_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
