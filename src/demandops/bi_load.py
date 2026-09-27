"""Load derived artifacts into the `bi` Postgres schema for the BI layer.

The stakeholder dashboard (Evidence.dev) reads from this curated schema, not
from raw CSVs — the standard transformation/BI split. Tables are derived from
the artifact columns each run (schema drift in the pipeline propagates
instead of breaking a hand-copied DDL) and reloaded atomically.

Tables:
- bi.risk_scores      <- data/processed/risk/risk_scores.csv
- bi.recommendations  <- data/processed/recommendations/recommendations.csv
- bi.simulation       <- newest data/processed/simulations/simulation_*.csv
"""

from __future__ import annotations

import sys

import pandas as pd
import psycopg

from demandops import config
from demandops.db import get_engine, psycopg_conninfo

TABLES = {
    "risk_scores": config.PROCESSED_DATA_DIR / "risk" / "risk_scores.csv",
    "recommendations": config.PROCESSED_DATA_DIR / "recommendations" / "recommendations.csv",
}
SIM_GLOB = "simulation_*.csv"


def _latest_simulation() -> pd.DataFrame | None:
    sims = sorted((config.PROCESSED_DATA_DIR / "simulations").glob(SIM_GLOB))
    if not sims:
        return None
    print(f"[info] simulation source: {sims[-1].name}")
    return pd.read_csv(sims[-1])


def _sources() -> dict[str, pd.DataFrame | None]:
    frames: dict[str, pd.DataFrame | None] = {}
    for table, path in TABLES.items():
        frames[table] = pd.read_csv(path) if path.exists() else None
    frames["simulation"] = _latest_simulation()
    return frames


def _reload(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> None:
    """Derive DDL from the frame, replace table contents atomically."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    for col in df.columns:
        if "data_gap" in col:
            df[col] = df[col].fillna(False).astype(bool)

    pg_types = {"int64": "BIGINT", "int32": "INTEGER",
                "float64": "DOUBLE PRECISION", "bool": "BOOLEAN",
                "boolean": "BOOLEAN", "object": "TEXT"}
    cols_sql = ", ".join(f"{c} {pg_types.get(str(df[c].dtype), 'TEXT')}"
                         for c in df.columns)
    conn.execute(f"DROP TABLE IF EXISTS bi.{table}")
    conn.execute(f"CREATE TABLE bi.{table} ({cols_sql})")

    cols = list(df.columns)
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)
    rows = [tuple(None if pd.isna(v) else v for v in row)
            for row in df.itertuples(index=False, name=None)]
    # executemany uses psycopg3 pipeline mode: one round-trip batch instead of
    # per-row WAN latency.
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO bi.{table} ({col_list}) VALUES ({placeholders})", rows)
    conn.commit()
    print(f"[ok] bi.{table}: {len(df)} rows reloaded")


def run() -> int:
    engine = get_engine()
    with psycopg.connect(**psycopg_conninfo()) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS bi")
        conn.commit()
        for table, df in _sources().items():
            if df is None:
                print(f"[skip] {table}: artifact missing — run the upstream "
                      "pipeline step first")
                continue
            _reload(conn, table, df)
    return 0


if __name__ == "__main__":
    sys.exit(run())
