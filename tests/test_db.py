"""Integration tests for the PostgreSQL layer.

These run only when DATABASE_URL is configured and the server is reachable;
otherwise they skip with a clear reason (unit tests must not require a DB).
"""

from __future__ import annotations

import pytest

from demandops import config, db

pytestmark = pytest.mark.db_integration


def _db_available() -> bool:
    if not config.database_url():
        return False
    try:
        db.get_engine().connect().close()
        return True
    except Exception:
        return False


if not _db_available():
    pytest.skip("DATABASE_URL not set or PostgreSQL unreachable", allow_module_level=True)

EXPECTED_ROWS = {
    "sales_train": 4_007_419,
    "sales_test": 47_021,
    "inventory": 5_432,
    "calendar": 23_016,
    "test_weights": 5_390,
}


def test_tables_loaded_with_expected_row_counts():
    with db.psycopg.connect(**db.psycopg_conninfo()) as conn:
        for table, expected in EXPECTED_ROWS.items():
            assert db.table_count(conn, table) == expected, table


def test_sales_train_dates_bounded():
    with db.psycopg.connect(**db.psycopg_conninfo()) as conn:
        lo, hi = conn.execute(
            "SELECT min(date), max(date) FROM rohlik.sales_train").fetchone()
    assert str(lo) == "2020-08-01"
    assert str(hi) == "2024-06-02"


def test_no_sales_rows_without_inventory_metadata():
    with db.psycopg.connect(**db.psycopg_conninfo()) as conn:
        orphans = conn.execute(
            "SELECT count(*) FROM rohlik.sales_train s "
            "LEFT JOIN rohlik.inventory i USING (unique_id) "
            "WHERE i.unique_id IS NULL").fetchone()[0]
    assert orphans == 0


def test_availability_stays_in_unit_range():
    with db.psycopg.connect(**db.psycopg_conninfo()) as conn:
        bad = conn.execute(
            "SELECT count(*) FROM rohlik.sales_train "
            "WHERE availability < 0 OR availability > 1").fetchone()[0]
    assert bad == 0
