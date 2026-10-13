"""Transformation module: creates cleaned staging models and an analysis-ready order mart in DuckDB."""
import time
import sys
from pathlib import Path
from typing import Dict, Optional, Any
import duckdb

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import config, logger, PipelineError

def create_staging_tables(conn: duckdb.DuckDBPyConnection) -> Dict[str, int]:
    """
    Build sanitized staging tables with normalized types and explicit NULL timestamps.
    Fully idempotent using CREATE OR REPLACE TABLE.
    """
    logger.info("Building staging models...")
    conn.execute("CREATE SCHEMA IF NOT EXISTS staging;")

    staging_counts: Dict[str, int] = {}

    # 1. staging.orders
    conn.execute("""
        CREATE OR REPLACE TABLE staging.orders AS
        SELECT 
            TRIM(order_id) AS order_id,
            TRIM(customer_id) AS customer_id,
            TRIM(order_status) AS order_status,
            TRY_CAST(order_purchase_timestamp AS TIMESTAMP) AS purchase_ts,
            TRY_CAST(order_approved_at AS TIMESTAMP) AS approved_ts,
            TRY_CAST(order_delivered_carrier_date AS TIMESTAMP) AS carrier_ts,
            TRY_CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_ts,
            TRY_CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated_ts
        FROM raw.orders;
    """)
    staging_counts["orders"] = conn.execute("SELECT COUNT(*) FROM staging.orders").fetchone()[0]

    # 2. staging.order_items
    conn.execute("""
        CREATE OR REPLACE TABLE staging.order_items AS
        SELECT 
            TRIM(order_id) AS order_id,
            CAST(order_item_id AS INTEGER) AS order_item_id,
            TRIM(product_id) AS product_id,
            TRIM(seller_id) AS seller_id,
            TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
            ROUND(CAST(price AS DOUBLE), 2) AS price,
            ROUND(CAST(freight_value AS DOUBLE), 2) AS freight_value
        FROM raw.order_items;
    """)
    staging_counts["order_items"] = conn.execute("SELECT COUNT(*) FROM staging.order_items").fetchone()[0]

    # 3. staging.payments
    conn.execute("""
        CREATE OR REPLACE TABLE staging.payments AS
        SELECT 
            TRIM(order_id) AS order_id,
            CAST(payment_sequential AS INTEGER) AS payment_sequential,
            TRIM(payment_type) AS payment_type,
            CAST(payment_installments AS INTEGER) AS payment_installments,
            ROUND(CAST(payment_value AS DOUBLE), 2) AS payment_value
        FROM raw.payments;
    """)
    staging_counts["payments"] = conn.execute("SELECT COUNT(*) FROM staging.payments").fetchone()[0]

    # 4. staging.reviews
    conn.execute("""
        CREATE OR REPLACE TABLE staging.reviews AS
        SELECT 
            TRIM(review_id) AS review_id,
            TRIM(order_id) AS order_id,
            CAST(review_score AS INTEGER) AS review_score,
            review_comment_title,
            review_comment_message,
            TRY_CAST(review_creation_date AS TIMESTAMP) AS review_creation_ts,
            TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_ts
        FROM raw.reviews;
    """)
    staging_counts["reviews"] = conn.execute("SELECT COUNT(*) FROM staging.reviews").fetchone()[0]

    # 5. staging.customers
    conn.execute("""
        CREATE OR REPLACE TABLE staging.customers AS
        SELECT 
            TRIM(customer_id) AS customer_id,
            TRIM(customer_unique_id) AS customer_unique_id,
            TRIM(customer_zip_code_prefix) AS customer_zip_code_prefix,
            TRIM(customer_city) AS customer_city,
            UPPER(TRIM(customer_state)) AS customer_state
        FROM raw.customers;
    """)
    staging_counts["customers"] = conn.execute("SELECT COUNT(*) FROM staging.customers").fetchone()[0]

    # 6. staging.products
    conn.execute("""
        CREATE OR REPLACE TABLE staging.products AS
        SELECT 
            TRIM(product_id) AS product_id,
            TRIM(product_category_name) AS product_category_name,
            TRY_CAST(product_name_lenght AS INTEGER) AS product_name_length,
            TRY_CAST(product_description_lenght AS INTEGER) AS product_description_length,
            TRY_CAST(product_photos_qty AS INTEGER) AS product_photos_qty,
            TRY_CAST(product_weight_g AS DOUBLE) AS product_weight_g,
            TRY_CAST(product_length_cm AS DOUBLE) AS product_length_cm,
            TRY_CAST(product_height_cm AS DOUBLE) AS product_height_cm,
            TRY_CAST(product_width_cm AS DOUBLE) AS product_width_cm
        FROM raw.products;
    """)
    staging_counts["products"] = conn.execute("SELECT COUNT(*) FROM staging.products").fetchone()[0]

    # Optional: category_translation
    tables_in_raw = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='raw'").fetchall()]
    if "category_translation" in tables_in_raw:
        conn.execute("""
            CREATE OR REPLACE TABLE staging.category_translation AS
            SELECT 
                TRIM(product_category_name) AS product_category_name,
                TRIM(product_category_name_english) AS product_category_name_english
            FROM raw.category_translation;
        """)
        staging_counts["category_translation"] = conn.execute("SELECT COUNT(*) FROM staging.category_translation").fetchone()[0]

    for tbl, count in staging_counts.items():
        logger.info("Staging model staging.%s created with %d rows.", tbl, count)

    return staging_counts

def create_order_mart(conn: duckdb.DuckDBPyConnection) -> int:
    """
    Build the order-level analytical mart: mart.order_summary.
    Guarantees:
      1. Exactly one row per order_id.
      2. No one-to-many join fanout (pre-aggregates line items, payments, and reviews separately).
      3. Precise delivery delay relative to estimated delivery date.
      4. Idempotent replacement.
    """
    logger.info("Building curated mart: mart.order_summary...")
    conn.execute("CREATE SCHEMA IF NOT EXISTS mart;")

    conn.execute("""
        CREATE OR REPLACE TABLE mart.order_summary AS
        WITH item_agg AS (
            -- Pre-aggregate items to prevent cartesian fanout with payments or reviews
            SELECT 
                order_id,
                ROUND(SUM(price), 2) AS item_total,
                ROUND(SUM(freight_value), 2) AS freight_total,
                ROUND(SUM(price + freight_value), 2) AS expected_order_total,
                COUNT(*) AS item_count
            FROM staging.order_items
            GROUP BY order_id
        ),
        payment_agg AS (
            -- Pre-aggregate payments separately
            SELECT 
                order_id,
                ROUND(SUM(payment_value), 2) AS payment_total,
                COUNT(*) AS payment_count,
                MAX(payment_installments) AS max_installments,
                STRING_AGG(DISTINCT payment_type, ', ') AS payment_types
            FROM staging.payments
            GROUP BY order_id
        ),
        review_agg AS (
            -- Pre-aggregate reviews per order (handles orders with multiple reviews)
            SELECT 
                order_id,
                ROUND(AVG(review_score), 2) AS review_score,
                COUNT(*) AS review_count
            FROM staging.reviews
            GROUP BY order_id
        )
        SELECT 
            o.order_id,
            o.customer_id,
            c.customer_unique_id,
            c.customer_state,
            o.order_status,
            o.purchase_ts,
            o.approved_ts,
            o.carrier_ts,
            o.delivered_ts,
            o.estimated_ts,
            
            -- Financial metrics
            COALESCE(i.item_total, 0.0) AS item_total,
            COALESCE(i.freight_total, 0.0) AS freight_total,
            COALESCE(i.expected_order_total, 0.0) AS gross_order_value,
            COALESCE(i.item_count, 0) AS item_count,
            COALESCE(p.payment_total, 0.0) AS payment_total,
            COALESCE(p.payment_count, 0) AS payment_count,
            p.max_installments,
            p.payment_types,
            
            -- Satisfaction metrics
            r.review_score,
            COALESCE(r.review_count, 0) AS review_count,
            
            -- Delivery logistics metrics
            CASE 
                WHEN o.delivered_ts IS NOT NULL AND o.estimated_ts IS NOT NULL 
                THEN ROUND(date_diff('second', o.estimated_ts, o.delivered_ts) / 86400.0, 2)
                ELSE NULL 
            END AS delivery_delay_days,
            
            CASE 
                WHEN o.delivered_ts IS NOT NULL AND o.purchase_ts IS NOT NULL 
                THEN ROUND(date_diff('second', o.purchase_ts, o.delivered_ts) / 86400.0, 2)
                ELSE NULL 
            END AS delivery_duration_days,

            -- Financial audit discrepancy flag (> 0.05 BRL difference)
            CASE 
                WHEN i.item_total IS NOT NULL AND p.payment_total IS NOT NULL 
                THEN ABS(i.expected_order_total - p.payment_total) > 0.05
                ELSE FALSE 
            END AS has_payment_discrepancy

        FROM staging.orders o
        LEFT JOIN staging.customers c ON o.customer_id = c.customer_id
        LEFT JOIN item_agg i ON o.order_id = i.order_id
        LEFT JOIN payment_agg p ON o.order_id = p.order_id
        LEFT JOIN review_agg r ON o.order_id = r.order_id;
    """)

    # Verify Invariants: Exactly 1 row per order_id and exact match with orders count
    orders_count = conn.execute("SELECT COUNT(*) FROM staging.orders").fetchone()[0]
    mart_count = conn.execute("SELECT COUNT(*) FROM mart.order_summary").fetchone()[0]
    distinct_orders = conn.execute("SELECT COUNT(DISTINCT order_id) FROM mart.order_summary").fetchone()[0]

    logger.info("Mart verification: orders=%d, mart_rows=%d, distinct_order_ids=%d", orders_count, mart_count, distinct_orders)
    if mart_count != orders_count:
        raise PipelineError(f"Mart row count invariant violated! Expected {orders_count}, got {mart_count}.")
    if mart_count != distinct_orders:
        raise PipelineError(f"Mart uniqueness invariant violated! {mart_count} total rows but only {distinct_orders} distinct order_ids.")

    logger.info("Mart mart.order_summary successfully verified with exactly %d unique order rows.", mart_count)
    return mart_count

def run_transformations(conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, Any]:
    """Execute complete staging and mart build."""
    should_close = False
    if conn is None:
        conn = duckdb.connect(str(config.duckdb_path))
        should_close = True

    try:
        staging_counts = create_staging_tables(conn)
        mart_rows = create_order_mart(conn)
        return {
            "staging": staging_counts,
            "mart_rows": mart_rows
        }
    finally:
        if should_close:
            conn.close()

if __name__ == "__main__":
    res = run_transformations()
    print("Transformation Result:", res)
