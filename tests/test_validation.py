"""Validation-layer tests.

Each test builds a small synthetic table with one deliberate defect and asserts
the check reports the expected explicit status. Bad data must surface as
FAIL/WARN with evidence — never be silently repaired or dropped.
"""

from __future__ import annotations

import pandas as pd
import pytest

from demandops import validation
from demandops.dataset import TableSpec


def make_spec(name: str = "fixture", business_key: list[str] | None = None) -> TableSpec:
    return TableSpec(
        name=name,
        path=None,  # type: ignore[arg-type]  # fixture specs never touch disk
        required_columns=["unique_id", "date", "warehouse", "sales"],
        dtypes={"unique_id": "int", "date": "date", "warehouse": "str", "sales": "float"},
        parse_dates=["date"],
        business_key=business_key or ["unique_id", "date"],
    )


def clean_frame(n_days: int = 5, n_ids: int = 2) -> pd.DataFrame:
    rows = []
    for uid in range(n_ids):
        for d in range(n_days):
            rows.append({"unique_id": uid, "date": pd.Timestamp(f"2024-01-0{d + 1}"),
                         "warehouse": "W_1", "sales": float(d + uid)})
    return pd.DataFrame(rows)


def test_clean_data_passes_all_checks():
    df = clean_frame()
    spec = make_spec()
    assert validation.check_schema(df, spec).status == "PASS"
    assert validation.check_missingness(df, spec).status == "PASS"
    assert validation.check_duplicates(df, spec).status == "PASS"
    assert validation.check_date_continuity(df, spec, group_col="warehouse").status == "PASS"
    assert validation.check_numeric_sanity(df, spec).status == "PASS"


def test_missing_required_column_fails_schema():
    df = clean_frame().drop(columns=["sales"])
    result = validation.check_schema(df, make_spec())
    assert result.status == "FAIL"
    assert result.details["missing_columns"] == ["sales"]


def test_wrong_dtype_fails_schema():
    df = clean_frame()
    df["sales"] = df["sales"].astype(str)  # numeric column loaded as text
    result = validation.check_schema(df, make_spec())
    assert result.status == "FAIL"
    assert "sales" in result.details["dtype_mismatches"]


def test_duplicate_business_key_fails():
    df = pd.concat([clean_frame(), clean_frame(n_days=1)], ignore_index=True)
    result = validation.check_duplicates(df, make_spec())
    assert result.status == "FAIL"
    # keep=False counts both copies; 2 ids x 1 day duplicated = 4 rows flagged.
    assert result.details["duplicate_rows"] == 4


def test_missing_date_is_flagged_not_repaired():
    df = clean_frame(n_days=5)
    df = df[df["date"] != pd.Timestamp("2024-01-03")]
    result = validation.check_date_continuity(df, make_spec(), group_col="warehouse")
    assert result.status == "WARN"
    assert result.details["missing_days_by_group"] == {"W_1": 1}


def test_negative_sales_fails_numeric_sanity():
    df = clean_frame()
    df.loc[0, "sales"] = -5.0
    result = validation.check_numeric_sanity(df, make_spec())
    assert result.status == "FAIL"
    assert result.details["impossible_values"]["negative_sales"] == 1


def test_discount_outlier_warns_but_is_not_a_fail():
    df = clean_frame()
    df["type_0_discount"] = [0.0, 0.1, 0.2, 1.5, 0.0] * 2  # 1.5 = anomalous fraction
    result = validation.check_numeric_sanity(df, make_spec(), max_outlier_pct=0.5)
    assert result.status == "WARN"
    assert result.details["outliers"]["type_0_discount_outside_0_1"] == 2
    assert sum(result.details["impossible_values"].values()) == 0


def test_material_discount_corruption_fails():
    # Real data has 32/4M rows corrupt (sparse -> WARN). A material share must FAIL.
    df = clean_frame(n_days=5, n_ids=20)  # 100 rows
    df["type_0_discount"] = -0.2  # every row corrupt
    result = validation.check_numeric_sanity(df, make_spec())
    assert result.status == "FAIL"


def test_null_heavy_column_warns():
    df = clean_frame()
    df.loc[0:2, "sales"] = None  # 3/10 nulls: WARN territory, not FAIL
    result = validation.check_missingness(df, make_spec())
    assert result.status == "WARN"
    assert result.details["columns_affected"]["sales"]["count"] == 3


def test_overwhelmingly_null_column_fails():
    df = clean_frame()
    df["sales"] = None  # 100% null
    result = validation.check_missingness(df, make_spec())
    assert result.status == "FAIL"


def test_referential_unknown_keys_fail():
    df = clean_frame()
    df["unique_id"] = [99, 99, 99, 99, 99, 98, 98, 98, 98, 98]
    result = validation.check_referential(
        df, make_spec(), "unique_id", pd.Series([1, 0]), "inventory")
    assert result.status == "FAIL"
    assert result.details["unknown_key_rows"] == 10


def test_coverage_extra_keys_warn_not_fail():
    df = clean_frame()
    df["unique_id"] = [7, 7, 7, 7, 7, 8, 8, 8, 8, 8]  # metadata-only ids
    result = validation.check_coverage(
        df, make_spec(), "unique_id", pd.Series([1, 0]), "sales_train")
    assert result.status == "WARN"
    assert result.details["extra_key_rows"] == 10


def test_overall_status_escalates_to_fail():
    results = [
        validation.CheckResult("a", "t", "PASS"),
        validation.CheckResult("b", "t", "WARN"),
        validation.CheckResult("c", "t", "FAIL"),
    ]
    assert validation.overall_status(results) == "FAIL"


@pytest.mark.parametrize("status", ["PASS", "WARN", "FAIL"])
def test_check_result_carries_status(status: str):
    r = validation.CheckResult("x", "t", status)
    assert r.status == status
