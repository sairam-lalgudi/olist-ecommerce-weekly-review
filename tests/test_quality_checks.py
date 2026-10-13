"""Tests for Data Quality assertions and the critical quality gate."""
import pytest
from src.ingest import ingest_raw_tables
from src.transform import create_staging_tables, create_order_mart
from src.quality_checks import run_quality_checks
from src.config import DataQualityError

def test_quality_checks_pass_on_clean_data(mem_db, synthetic_data_dir):
    """Verify that quality checks execute and pass the gate on valid synthetic data."""
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    create_order_mart(mem_db)

    results = run_quality_checks(conn=mem_db)
    assert len(results) == 7
    # Ensure no critical check has status 'FAIL'
    critical_fails = [r for r in results if r["severity"] == "CRITICAL" and r["status"] == "FAIL"]
    assert len(critical_fails) == 0

def test_quality_gate_raises_on_critical_duplicate_order_id(mem_db, synthetic_data_dir):
    """Verify that injecting a duplicate order_id triggers a critical failure and raises DataQualityError."""
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    
    # Deliberately inject duplicate primary key into staging.orders
    mem_db.execute("""
        INSERT INTO staging.orders (order_id, customer_id, order_status)
        VALUES ('ord_001', 'cust_injected_dup', 'delivered');
    """)

    with pytest.raises(DataQualityError) as exc_info:
        run_quality_checks(conn=mem_db)
    
    assert "Quality Gate Failed" in str(exc_info.value)
    assert "check_1_null_or_duplicate_order_id" in str(exc_info.value)

def test_quality_gate_raises_on_delivery_before_purchase(mem_db, synthetic_data_dir):
    """Verify that delivering an order before purchase date raises DataQualityError."""
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    
    # Invert timestamps: purchase on 2017-05-10, delivered on 2017-05-01
    mem_db.execute("""
        INSERT INTO staging.orders (order_id, customer_id, order_status, purchase_ts, delivered_ts)
        VALUES ('ord_bad_time', 'cust_001', 'delivered', '2017-05-10 00:00:00'::timestamp, '2017-05-01 00:00:00'::timestamp);
    """)

    with pytest.raises(DataQualityError) as exc_info:
        run_quality_checks(conn=mem_db)
    
    assert "check_2_delivered_before_purchase" in str(exc_info.value)
