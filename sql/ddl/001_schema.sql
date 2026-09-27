-- DemandOps schema for the Rohlik dataset.
-- Raw CSVs are loaded verbatim via COPY; validation is the gate upstream,
-- the database is the analytical substrate. All types are explicit.

CREATE SCHEMA IF NOT EXISTS rohlik;

CREATE TABLE IF NOT EXISTS rohlik.warehouses (
    warehouse TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS rohlik.inventory (
    unique_id          BIGINT PRIMARY KEY,
    product_unique_id  BIGINT NOT NULL,
    name               TEXT NOT NULL,
    l1_category_name_en TEXT,
    l2_category_name_en TEXT,
    l3_category_name_en TEXT,
    l4_category_name_en TEXT,
    warehouse          TEXT NOT NULL REFERENCES rohlik.warehouses (warehouse)
);

CREATE TABLE IF NOT EXISTS rohlik.calendar (
    warehouse               TEXT NOT NULL REFERENCES rohlik.warehouses (warehouse),
    date                    DATE NOT NULL,
    holiday_name            TEXT,
    holiday                 SMALLINT NOT NULL,
    shops_closed            SMALLINT NOT NULL,
    winter_school_holidays  SMALLINT NOT NULL,
    school_holidays         SMALLINT NOT NULL,
    PRIMARY KEY (warehouse, date)
);

CREATE TABLE IF NOT EXISTS rohlik.sales_train (
    unique_id        BIGINT NOT NULL,
    date             DATE NOT NULL,
    warehouse        TEXT NOT NULL REFERENCES rohlik.warehouses (warehouse),
    total_orders     DOUBLE PRECISION,
    sales            DOUBLE PRECISION,
    sell_price_main  DOUBLE PRECISION,
    availability     DOUBLE PRECISION,
    type_0_discount  DOUBLE PRECISION,
    type_1_discount  DOUBLE PRECISION,
    type_2_discount  DOUBLE PRECISION,
    type_3_discount  DOUBLE PRECISION,
    type_4_discount  DOUBLE PRECISION,
    type_5_discount  DOUBLE PRECISION,
    type_6_discount  DOUBLE PRECISION,
    PRIMARY KEY (unique_id, date)
);

CREATE TABLE IF NOT EXISTS rohlik.sales_test (
    unique_id        BIGINT NOT NULL,
    date             DATE NOT NULL,
    warehouse        TEXT NOT NULL REFERENCES rohlik.warehouses (warehouse),
    total_orders     DOUBLE PRECISION,
    sell_price_main  DOUBLE PRECISION,
    type_0_discount  DOUBLE PRECISION,
    type_1_discount  DOUBLE PRECISION,
    type_2_discount  DOUBLE PRECISION,
    type_3_discount  DOUBLE PRECISION,
    type_4_discount  DOUBLE PRECISION,
    type_5_discount  DOUBLE PRECISION,
    type_6_discount  DOUBLE PRECISION,
    PRIMARY KEY (unique_id, date)
);

CREATE TABLE IF NOT EXISTS rohlik.test_weights (
    unique_id  BIGINT PRIMARY KEY,
    weight     DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_train_warehouse ON rohlik.sales_train (warehouse);
CREATE INDEX IF NOT EXISTS idx_sales_train_date ON rohlik.sales_train (date);
