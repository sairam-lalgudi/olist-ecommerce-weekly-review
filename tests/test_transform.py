"""Tests for staging models, one-row-per-order mart invariants, and fanout prevention."""
import pytest
from src.ingest import ingest_raw_tables
from src.transform import create_staging_tables, create_order_mart

def test_staging_and_mart_creation(mem_db, synthetic_data_dir):
    """Verify that staging and mart tables are correctly constructed from synthetic data."""
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    staging_counts = create_staging_tables(mem_db)
    assert staging_counts["orders"] == 4
    assert staging_counts["order_items"] == 5

    mart_rows = create_order_mart(mem_db)
    assert mart_rows == 4

def test_mart_one_row_per_order_invariant(mem_db, synthetic_data_dir):
    """Verify that mart.order_summary maintains the absolute invariant of 1 row per order."""
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    create_order_mart(mem_db)

    row = mem_db.execute("""
        SELECT 
            COUNT(*) AS total_rows,
            COUNT(DISTINCT order_id) AS distinct_orders
        FROM mart.order_summary
    """).fetchone()

    total_rows, distinct_orders = row[0], row[1]
    assert total_rows == 4
    assert total_rows == distinct_orders, "Mart failed 1-row-per-order uniqueness invariant!"

def test_fanout_prevention_on_multi_item_payments(mem_db, synthetic_data_dir):
    """
    CRITICAL BIG DATA INVARIANT:
    Order 'ord_001' has 2 line items and 2 payments.
    A naive 1-to-many join produces 4 Cartesian rows, falsely doubling revenues and payments.
    Pre-aggregating ensures exactly 1 row with exact totals:
      - item_total = 150.00 (100 + 50)
      - freight_total = 25.00 (15 + 10)
      - payment_total = 175.00 (25 + 150)
      - review_score = 5.00
    """
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    create_order_mart(mem_db)

    ord1 = mem_db.execute("""
        SELECT 
            order_id, item_total, freight_total, gross_order_value, 
            payment_total, item_count, payment_count, review_score
        FROM mart.order_summary
        WHERE order_id = 'ord_001'
    """).fetchone()

    assert ord1[0] == "ord_001"
    assert ord1[1] == 150.00, f"Expected item_total=150.00, got {ord1[1]} (fanout detected!)"
    assert ord1[2] == 25.00, f"Expected freight_total=25.00, got {ord1[2]} (fanout detected!)"
    assert ord1[3] == 175.00, f"Expected gross_order_value=175.00, got {ord1[3]}"
    assert ord1[4] == 175.00, f"Expected payment_total=175.00, got {ord1[4]}"
    assert ord1[5] == 2, f"Expected item_count=2, got {ord1[5]}"
    assert ord1[6] == 2, f"Expected payment_count=2, got {ord1[6]}"
    assert ord1[7] == 5.00, f"Expected review_score=5.00, got {ord1[7]}"

def test_delivery_delay_calculation(mem_db, synthetic_data_dir):
    """
    Verify delivery delay logic:
    - ord_001 delivered on 2017-01-18, estimated was 2017-01-25 -> delivered 6.33 days early (negative)
    - ord_002 delivered on 2017-01-22, estimated was 2017-01-20 -> delivered 2.75 days late (positive)
    """
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    create_order_mart(mem_db)

    res = mem_db.execute("""
        SELECT order_id, delivery_delay_days
        FROM mart.order_summary
        WHERE order_id IN ('ord_001', 'ord_002')
        ORDER BY order_id
    """).fetchall()

    ord1_delay, ord2_delay = res[0][1], res[1][1]
    assert ord1_delay < 0, f"ord_001 should be early (negative delay), got {ord1_delay}"
    assert ord2_delay > 0, f"ord_002 should be late (positive delay), got {ord2_delay}"
