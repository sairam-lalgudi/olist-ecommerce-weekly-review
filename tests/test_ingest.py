"""Tests for raw ingestion, schema validation, and idempotency using synthetic fixtures."""
import pytest
from src.ingest import ingest_raw_tables, validate_csv_columns
from src.config import MissingColumnError, MissingFileError

def test_ingest_synthetic_tables(mem_db, synthetic_data_dir):
    """Verify that all synthetic CSV tables are ingested into raw.* schema."""
    counts = ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    assert counts["orders"] == 4
    assert counts["order_items"] == 5
    assert counts["payments"] == 5
    assert counts["reviews"] == 3
    assert counts["customers"] == 4
    assert counts["products"] == 2

    # Check that DuckDB raw tables exist
    res = mem_db.execute("SELECT COUNT(*) FROM raw.orders").fetchone()[0]
    assert res == 4

def test_ingest_idempotency(mem_db, synthetic_data_dir):
    """Verify that repeatedly running ingestion does NOT duplicate records."""
    counts1 = ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    assert counts1["orders"] == 4

    # Second run on same DB connection
    counts2 = ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    assert counts2["orders"] == 4

    # Direct query assertion
    orders_total = mem_db.execute("SELECT COUNT(*) FROM raw.orders").fetchone()[0]
    assert orders_total == 4, "Idempotency failed: rows duplicated on second ingestion run!"

def test_missing_column_validation_fails(mem_db, tmp_path):
    """Verify that MissingColumnError is raised when a required column is missing."""
    bad_csv = tmp_path / "olist_orders_dataset.csv"
    # Missing customer_id column
    bad_csv.write_text("order_id,order_status,order_purchase_timestamp\nord1,delivered,2017-01-01\n")
    
    with pytest.raises(MissingColumnError) as exc_info:
        validate_csv_columns(mem_db, "orders", bad_csv, ["order_id", "customer_id", "order_status"])
    assert "missing required columns" in str(exc_info.value)
