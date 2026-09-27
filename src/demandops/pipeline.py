"""Ingestion + validation pipeline (Layer 1).

Loads every raw table, runs the full check battery, plus cross-table
referential checks, then writes:
- data_quality_reports/validation_report_<timestamp>.json (full evidence)
- data_quality_reports/run_manifest_<timestamp>.json      (run traceability)

Exits nonzero if any check is FAIL — downstream stages must not proceed on
invalid data.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd

from demandops import config, dataset, manifest, validation
from demandops.validation import CheckResult, overall_status


def run() -> tuple[str, list[CheckResult]]:
    results: list[CheckResult] = []
    inputs: dict[str, int] = {}
    tables: dict[str, pd.DataFrame] = {}

    # Load every table exactly once, then run checks against the in-memory copy.
    for name in dataset.TABLES:
        tables[name] = dataset.load_table(name)
        inputs[name] = len(tables[name])

    for name, spec in dataset.TABLES.items():
        df = tables[name]
        for check in validation.ALL_CHECKS:
            if check is validation.check_date_continuity:
                group = "warehouse" if "warehouse" in df.columns else None
                results.append(check(df, spec, group_col=group))
            else:
                results.append(check(df, spec))
        print(f"validated table '{name}': {len(df)} rows")

    # Cross-table referential integrity.
    # Hard direction: every sales/weights id must exist in inventory (FAIL).
    results.append(validation.check_referential(
        tables["sales_train"], dataset.TABLES["sales_train"], "unique_id",
        tables["inventory"]["unique_id"], "inventory"))
    for name in ("sales_test", "test_weights"):
        results.append(validation.check_referential(
            tables[name], dataset.TABLES[name], "unique_id",
            tables["inventory"]["unique_id"], "inventory"))
    # Soft direction: inventory may legitimately carry metadata for products
    # with no sales rows; report as coverage evidence (WARN), do not block.
    results.append(validation.check_coverage(
        tables["inventory"], dataset.TABLES["inventory"], "unique_id",
        tables["sales_train"]["unique_id"], "sales_train"))

    del tables

    overall = overall_status(results)
    summary = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "WARN", "FAIL")}
    summary["overall"] = overall

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "checks": [vars(r) for r in results],
    }
    report_path = config.REPORTS_DIR / (
        f"validation_report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    manifest.write_manifest(
        kind="ingestion_validation",
        inputs=inputs,
        outputs={"validation_report": str(report_path.relative_to(config.PROJECT_ROOT))},
        validation_summary=summary,
    )
    return overall, results


def main() -> int:
    overall, results = run()
    print("\n=== Validation report ===")
    for r in results:
        if r.status != "PASS":
            print(r.summary_line())
    n_pass = sum(1 for r in results if r.status == "PASS")
    print(f"{n_pass}/{len(results)} checks passed; overall: {overall}")
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
