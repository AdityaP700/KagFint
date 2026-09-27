"""Data validation checks.

Every check returns an explicit CheckResult with PASS / WARN / FAIL status and
quantified evidence. Nothing is silently repaired or dropped: the caller decides
what to do based on the report.

Status semantics:
- PASS: check ran, no issue found.
- WARN: issue found and quantified; pipeline may continue but the report must surface it.
- FAIL: data is invalid for downstream use (schema drift, business-key duplicates,
  impossible values). Downstream stages must not proceed on FAIL without a
  documented decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_SEVERITY = {PASS: 0, WARN: 1, FAIL: 2}


@dataclass
class CheckResult:
    name: str
    table: str
    status: str
    details: dict = field(default_factory=dict)

    def summary_line(self) -> str:
        return f"[{self.status}] {self.table}:{self.name} {self.details}"


def _dtype_family(series: pd.Series, expected: str) -> bool:
    # Accept both family names ("int") and concrete dtype strings ("int64").
    if expected.startswith("int"):
        return pd.api.types.is_integer_dtype(series)
    if expected.startswith("float"):
        return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    if expected.startswith("str"):
        return pd.api.types.is_object_dtype(series) or isinstance(series.dtype, pd.StringDtype)
    if expected.startswith("date"):
        return pd.api.types.is_datetime64_any_dtype(series)
    return False


def check_schema(df: pd.DataFrame, spec) -> CheckResult:
    missing = [c for c in spec.required_columns if c not in df.columns]
    unexpected = [c for c in df.columns if c not in spec.required_columns]
    dtype_mismatches = {
        c: str(df[c].dtype)
        for c in spec.required_columns
        if c in df.columns
        and not _dtype_family(
            df[c], "date" if c in spec.parse_dates else spec.dtypes[c]
        )
    }
    status = PASS if not (missing or dtype_mismatches) else FAIL
    if unexpected:
        status = WARN if status == PASS else status
    return CheckResult(
        name="schema", table=spec.name, status=status,
        details={"missing_columns": missing, "unexpected_columns": unexpected,
                 "dtype_mismatches": dtype_mismatches},
    )


def check_missingness(df: pd.DataFrame, spec, max_fail_pct: float = 0.5) -> CheckResult:
    """Report null counts per column.

    Columns listed in spec.nullable_by_design are null by business semantics
    (e.g. holiday_name is null when there is no holiday); their nulls are
    reported but never escalate the status.
    """
    null_counts = df.isna().sum()
    by_design = set(getattr(spec, "nullable_by_design", []))
    affected = {
        c: {"count": int(n), "pct": round(float(n) / len(df), 6)}
        for c, n in null_counts.items() if n > 0
    }
    if not affected:
        return CheckResult(name="missingness", table=spec.name, status=PASS, details={"columns_affected": {}})
    blocking = {c: v for c, v in affected.items() if c not in by_design}
    if not blocking:
        return CheckResult(
            name="missingness", table=spec.name, status=PASS,
            details={"columns_affected": affected,
                     "note": "nulls are nullable-by-design columns"},
        )
    worst = max(v["pct"] for v in blocking.values())
    status = FAIL if worst > max_fail_pct else WARN
    return CheckResult(name="missingness", table=spec.name, status=status,
                       details={"columns_affected": affected, "worst_pct": worst})


def check_duplicates(df: pd.DataFrame, spec) -> CheckResult:
    if not spec.business_key:
        return CheckResult(name="duplicates", table=spec.name, status=PASS,
                           details={"skipped": "no business key declared"})
    key = spec.business_key
    dup_mask = df.duplicated(subset=key, keep=False)
    dup_rows = int(dup_mask.sum())
    dup_keys = int(df.loc[dup_mask].groupby(key, dropna=False).ngroups)
    status = FAIL if dup_rows > 0 else PASS
    return CheckResult(name="duplicates", table=spec.name, status=status,
                       details={"key": key, "duplicate_rows": dup_rows, "duplicate_key_groups": dup_keys})


def check_date_continuity(df: pd.DataFrame, spec, group_col: str | None = None) -> CheckResult:
    if "date" not in df.columns or df.empty:
        return CheckResult(name="date_continuity", table=spec.name, status=PASS,
                           details={"skipped": "no date column or empty table"})
    by_group: dict[str, int] = {}
    groups = df.groupby(group_col) if group_col else [(None, df)]
    for gval, g in groups:
        days = pd.Series(pd.to_datetime(g["date"].unique())).sort_values()
        expected = pd.date_range(days.min(), days.max(), freq="D")
        missing = int(len(expected) - len(days))
        if missing:
            by_group[str(gval)] = missing
    status = WARN if by_group else PASS
    return CheckResult(name="date_continuity", table=spec.name, status=status,
                       details={"missing_days_by_group": by_group,
                                "min_date": str(df["date"].min().date()),
                                "max_date": str(df["date"].max().date())})


def check_numeric_sanity(df: pd.DataFrame, spec, max_outlier_pct: float = 0.001) -> CheckResult:
    """Business rules. Impossible values FAIL; sparse anomalies WARN.

    Negative sales/prices and availability outside [0,1] are impossible -> FAIL.
    Discount fractions outside [0,1] (including negatives as low as -20 in the
    real data) are corrupt values but sparse; they are reported as quantified
    outliers with rows preserved, and escalate to FAIL only when they exceed
    max_outlier_pct of rows — i.e. when the corruption is material.
    """
    impossible: dict[str, int] = {}
    outliers: dict[str, int] = {}
    if "sales" in df.columns:
        impossible["negative_sales"] = int((df["sales"] < 0).sum())
    if "sell_price_main" in df.columns:
        impossible["negative_price"] = int((df["sell_price_main"] < 0).sum())
    if "availability" in df.columns:
        impossible["availability_outside_0_1"] = int(
            ((df["availability"] < 0) | (df["availability"] > 1)).sum())
    for c in df.columns:
        if c.endswith("_discount"):
            outside = int(((df[c] < 0) | (df[c] > 1)).sum())
            outliers[f"{c}_outside_0_1"] = outside
    total_impossible = sum(impossible.values())
    total_outliers = sum(outliers.values())
    if total_impossible > 0:
        status = FAIL
    elif total_outliers > max_outlier_pct * len(df):
        status = FAIL
    elif total_outliers > 0:
        status = WARN
    else:
        status = PASS
    return CheckResult(name="numeric_sanity", table=spec.name, status=status,
                       details={"impossible_values": impossible, "outliers": outliers})


def check_referential(
    df: pd.DataFrame, spec, foreign_key: str, referenced: pd.Series, ref_table: str
) -> CheckResult:
    """Every foreign key value must exist in the referenced table's key set."""
    known = set(referenced.unique())
    unknown = df.loc[~df[foreign_key].isin(known), foreign_key]
    status = FAIL if len(unknown) > 0 else PASS
    return CheckResult(
        name=f"referential_{foreign_key}->{ref_table}", table=spec.name, status=status,
        details={"unknown_key_rows": int(len(unknown)),
                 "unknown_key_examples": sorted(map(str, unknown.unique()[:10]))},
    )


def check_coverage(
    df: pd.DataFrame, spec, key: str, referenced: pd.Series, ref_table: str
) -> CheckResult:
    """Soft direction of referential integrity: df holds a superset of keys.

    Used when extra keys in df are legitimate metadata (e.g. inventory rows for
    products that never sold) — reported as WARN evidence, not a blocker.
    """
    known = set(referenced.unique())
    extra = df.loc[~df[key].isin(known), key]
    status = WARN if len(extra) > 0 else PASS
    return CheckResult(
        name=f"coverage_{key}_not_in_{ref_table}", table=spec.name, status=status,
        details={"extra_key_rows": int(len(extra)),
                 "extra_key_examples": sorted(map(str, extra.unique()[:10]))},
    )


ALL_CHECKS: list[Callable[[pd.DataFrame, "object"], CheckResult]] = [
    check_schema, check_missingness, check_duplicates,
    check_date_continuity, check_numeric_sanity,
]


def overall_status(results: list[CheckResult]) -> str:
    return max((r.status for r in results), key=lambda s: _SEVERITY[s])
