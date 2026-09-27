"""Dataset registry: raw table locations, expected schemas, and loaders.

The raw directory is treated as immutable. Loaders never write to it.
Expected schemas are declared explicitly so the validation layer can fail
loudly on drift instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from demandops import config

RAW_DIR = config.RAW_DATA_DIR / "rohlik-sales-forecasting-challenge-v2"

# Dtype families used by the validator: "int", "float", "str", "date".
SALES_COLUMNS = [
    "unique_id", "date", "warehouse", "total_orders", "sales",
    "sell_price_main", "availability",
    "type_0_discount", "type_1_discount", "type_2_discount", "type_3_discount",
    "type_4_discount", "type_5_discount", "type_6_discount",
]
SALES_TEST_COLUMNS = [c for c in SALES_COLUMNS if c not in ("sales", "availability")]


@dataclass(frozen=True)
class TableSpec:
    name: str
    path: Path
    required_columns: list[str]
    dtypes: dict[str, str]
    parse_dates: list[str] = field(default_factory=list)
    business_key: list[str] = field(default_factory=list)
    # Columns whose nulls are semantically correct (never escalate missingness).
    nullable_by_design: list[str] = field(default_factory=list)


TABLES: dict[str, TableSpec] = {
    "sales_train": TableSpec(
        name="sales_train",
        path=RAW_DIR / "sales_train.csv",
        required_columns=SALES_COLUMNS,
        dtypes={
            "unique_id": "int64", "warehouse": "str", "total_orders": "float64",
            "sales": "float64", "sell_price_main": "float64", "availability": "float64",
            **{f"type_{i}_discount": "float64" for i in range(7)},
        },
        parse_dates=["date"],
        business_key=["unique_id", "date"],
    ),
    "sales_test": TableSpec(
        name="sales_test",
        path=RAW_DIR / "sales_test.csv",
        required_columns=SALES_TEST_COLUMNS,
        dtypes={
            "unique_id": "int64", "warehouse": "str", "total_orders": "float64",
            "sell_price_main": "float64",
            **{f"type_{i}_discount": "float64" for i in range(7)},
        },
        parse_dates=["date"],
        business_key=["unique_id", "date"],
    ),
    "inventory": TableSpec(
        name="inventory",
        path=RAW_DIR / "inventory.csv",
        required_columns=[
            "unique_id", "product_unique_id", "name",
            "L1_category_name_en", "L2_category_name_en", "L3_category_name_en",
            "L4_category_name_en", "warehouse",
        ],
        dtypes={
            "unique_id": "int64", "product_unique_id": "int64", "name": "str",
            "L1_category_name_en": "str", "L2_category_name_en": "str",
            "L3_category_name_en": "str", "L4_category_name_en": "str",
            "warehouse": "str",
        },
        business_key=["unique_id"],
    ),
    "calendar": TableSpec(
        name="calendar",
        path=RAW_DIR / "calendar.csv",
        required_columns=[
            "date", "holiday_name", "holiday", "shops_closed",
            "winter_school_holidays", "school_holidays", "warehouse",
        ],
        dtypes={
            "holiday_name": "str", "holiday": "int64", "shops_closed": "int64",
            "winter_school_holidays": "int64", "school_holidays": "int64",
            "warehouse": "str",
        },
        parse_dates=["date"],
        business_key=["warehouse", "date"],
        # holiday_name is null exactly when holiday == 0: no holiday that day.
        nullable_by_design=["holiday_name"],
    ),
    "test_weights": TableSpec(
        name="test_weights",
        path=RAW_DIR / "test_weights.csv",
        required_columns=["unique_id", "weight"],
        dtypes={"unique_id": "int64", "weight": "float64"},
        business_key=["unique_id"],
    ),
}


def load_table(name: str) -> pd.DataFrame:
    """Load a raw table with the declared dtypes. Raises if the file is missing."""
    spec = TABLES[name]
    if not spec.path.exists():
        raise FileNotFoundError(
            f"Raw file for table '{name}' not found at {spec.path}. "
            "Download and extract the dataset into data/raw/ first."
        )
    df = pd.read_csv(spec.path, dtype=spec.dtypes, parse_dates=spec.parse_dates)
    return df
