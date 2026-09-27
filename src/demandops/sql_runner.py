"""Run the SQL analytics layer.

Executes every query in sql/analytics/ sequentially (single connection, one at
a time — light on the machine), saves each result as CSV under
data/processed/analytics/, and writes one run manifest for the batch.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

import pandas as pd

from demandops import config, manifest
from demandops.db import get_engine

OUT_DIR = config.PROCESSED_DATA_DIR / "analytics"


def run_all() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    queries = sorted(config.SQL_DIR.glob("analytics/*.sql"))
    if not queries:
        print("no analytics queries found")
        return 1

    engine = get_engine()
    inputs: dict[str, int] = {}
    outputs: dict[str, str] = {}
    failures: list[str] = []

    for qpath in queries:
        name = qpath.stem
        sql = qpath.read_text(encoding="utf-8")
        t0 = time.perf_counter()
        try:
            df = pd.read_sql_query(sa_text(sql), engine)
        except Exception as e:
            failures.append(f"{name}: {type(e).__name__}: {e}")
            print(f"[FAIL] {name}: {e}")
            continue
        elapsed = time.perf_counter() - t0
        out = OUT_DIR / f"{name}.csv"
        df.to_csv(out, index=False)
        outputs[name] = str(out.relative_to(config.PROJECT_ROOT))
        inputs[name] = len(df)
        print(f"[ok] {name}: {len(df)} rows in {elapsed:.1f}s")

    summary = {
        "PASS": len(outputs), "FAIL": len(failures),
        "overall": "FAIL" if failures else "PASS",
    }
    manifest.write_manifest(
        kind="sql_analytics",
        inputs=inputs,
        outputs=outputs,
        validation_summary=summary,
        extra={"failures": failures,
               "generated_at": datetime.now(timezone.utc).isoformat()},
    )
    return 1 if failures else 0


def sa_text(sql: str):
    import sqlalchemy as sa
    return sa.text(sql)


if __name__ == "__main__":
    sys.exit(run_all())
