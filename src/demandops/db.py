"""PostgreSQL layer: connection, schema application, and COPY-based loading.

Credentials come exclusively from DATABASE_URL in the environment/.env and are
never printed or logged. Loading is idempotent: a non-empty table is skipped
unless --force (which truncates and reloads). Every load is verified by row
count against the source CSV and recorded in a run manifest.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import psycopg
import sqlalchemy as sa

from demandops import config, dataset, manifest

DDL_PATH = config.SQL_DIR / "ddl" / "001_schema.sql"

SCHEMA_NAME = "rohlik"
# DB table -> (source CSV stem, DB column order). CSV column order matches the
# raw files; COPY maps by the explicit column list.
TABLE_COLUMNS: dict[str, list[str]] = {
    "sales_train": dataset.SALES_COLUMNS,
    "sales_test": dataset.SALES_TEST_COLUMNS,
    "inventory": [
        "unique_id", "product_unique_id", "name",
        "l1_category_name_en", "l2_category_name_en", "l3_category_name_en",
        "l4_category_name_en", "warehouse",
    ],
    "calendar": [
        "date", "holiday_name", "holiday", "shops_closed",
        "winter_school_holidays", "school_holidays", "warehouse",
    ],
    "test_weights": ["unique_id", "weight"],
}

LOAD_ORDER = ["inventory", "calendar", "sales_test", "test_weights", "sales_train"]


def get_url() -> str:
    url = config.database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env (see .env.example); "
            "the database layer never guesses credentials."
        )
    return url


def get_engine() -> sa.Engine:
    return sa.create_engine(get_url())


def csv_profile(path: Path) -> tuple[int, set[str]]:
    """One streaming pass: returns (data-row count, distinct warehouse values)."""
    rows = 0
    warehouses: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        has_wh = reader.fieldnames is not None and "warehouse" in reader.fieldnames
        for row in reader:
            rows += 1
            if has_wh and row["warehouse"]:
                warehouses.add(row["warehouse"])
    return rows, warehouses


def psycopg_conninfo(database: str | None = None) -> dict:
    """SQLAlchemy URL -> psycopg connection kwargs (never logged)."""
    p = sa.engine.make_url(get_url()).translate_connect_args()
    p["dbname"] = database or p["database"]
    p.pop("database", None)
    p["user"] = p.pop("username", None)
    return {k: v for k, v in p.items() if v is not None}


def ensure_database() -> None:
    """Create the target database if it does not exist (maintenance connection)."""
    url = sa.engine.make_url(get_url())
    database = url.database
    if not database:
        raise RuntimeError("DATABASE_URL must include a database name.")
    with psycopg.connect(**psycopg_conninfo("postgres")) as conn:
        conn.autocommit = True
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{database}"')
            print(f"created database '{database}'")
        else:
            print(f"database '{database}' already exists")


def apply_schema(engine: sa.Engine) -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)
    print(f"schema applied from {DDL_PATH.relative_to(config.PROJECT_ROOT)}")


def seed_warehouses(conn: psycopg.Connection, warehouses: set[str]) -> int:
    inserted = 0
    for w in sorted(warehouses):
        cur = conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.warehouses (warehouse) VALUES (%s) "
            "ON CONFLICT DO NOTHING",
            (w,),
        )
        inserted += cur.rowcount
    return inserted


def copy_csv(conn: psycopg.Connection, table: str, path: Path) -> None:
    columns = TABLE_COLUMNS[table]
    col_list = ", ".join(columns)
    with conn.cursor() as cur, cur.copy(
        f"COPY {SCHEMA_NAME}.{table} ({col_list}) FROM STDIN "
        "WITH (FORMAT csv, HEADER true, NULL '')"
    ) as copy, path.open("rb") as f:
        while chunk := f.read(1 << 20):
            copy.write(chunk)


def table_count(conn: psycopg.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{table}").fetchone()[0])


def load_all(force: bool = False) -> dict[str, int]:
    engine = get_engine()
    profiles: dict[str, tuple[int, set[str]]] = {}
    all_warehouses: set[str] = set()
    for table in LOAD_ORDER:
        path = dataset.TABLES[table].path
        profiles[table] = csv_profile(path)
        all_warehouses |= profiles[table][1]

    loaded: dict[str, int] = {}
    with psycopg.connect(**psycopg_conninfo()) as conn:
        seed_warehouses(conn, all_warehouses)
        conn.commit()
        for table in LOAD_ORDER:
            expected, _ = profiles[table]
            current = table_count(conn, table)
            if current == expected:
                print(f"{table}: already loaded ({current} rows), skipping")
                loaded[table] = current
                continue
            if current > 0 and not force:
                print(f"{table}: {current} rows present vs {expected} expected; "
                      "use --force to truncate and reload")
                loaded[table] = current
                continue
            if current > 0 and force:
                conn.execute(f"TRUNCATE {SCHEMA_NAME}.{table}")
            copy_csv(conn, table, dataset.TABLES[table].path)
            conn.commit()
            actual = table_count(conn, table)
            if actual != expected:
                raise RuntimeError(
                    f"load verification failed for {table}: {actual} rows in DB "
                    f"vs {expected} in CSV"
                )
            print(f"{table}: loaded {actual} rows (matches CSV)")
            loaded[table] = actual

        # Final referential sanity inside the database itself.
        orphans = int(conn.execute(
            f"SELECT count(*) FROM {SCHEMA_NAME}.sales_train s "
            f"LEFT JOIN {SCHEMA_NAME}.inventory i USING (unique_id) "
            "WHERE i.unique_id IS NULL"
        ).fetchone()[0])
        if orphans:
            raise RuntimeError(f"{orphans} sales_train rows have no inventory metadata")
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply schema and load raw data.")
    parser.add_argument("--force", action="store_true",
                        help="truncate non-empty tables and reload")
    args = parser.parse_args()

    ensure_database()
    engine = get_engine()
    apply_schema(engine)
    loaded = load_all(force=args.force)

    manifest.write_manifest(
        kind="db_load",
        inputs=loaded,
        outputs={"database": sa.engine.make_url(get_url()).database,
                 "schema": SCHEMA_NAME},
        validation_summary={"overall": "PASS", "note": "row counts verified against CSVs"},
    )
    print("manifest written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
