"""Tests for Part C analytical queries and metric logic using synthetic fixtures."""
import pytest
from src.ingest import ingest_raw_tables
from src.transform import create_staging_tables, create_order_mart
from src.config import config

@pytest.fixture(autouse=True)
def setup_synthetic_warehouse(mem_db, synthetic_data_dir):
    """Automatically populate in-memory database with synthetic staging and mart tables."""
    ingest_raw_tables(conn=mem_db, data_dir=synthetic_data_dir)
    create_staging_tables(mem_db)
    create_order_mart(mem_db)

def test_query_01_mom_revenue_growth(mem_db):
    """Test Question 1: LAG window function on monthly revenue."""
    with open(config.sql_analysis_dir / "01_monthly_revenue_growth.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    
    rows = mem_db.execute(sql).fetchall()
    # In synthetic data: ord_001 (175) and ord_002 (225) in 2017-01 -> 400.00
    # ord_003 (138) in 2017-02 -> 138.00 (ord_004 canceled, excluded)
    assert len(rows) == 2
    jan_row, feb_row = rows[0], rows[1]
    assert jan_row[1] == 400.00  # Jan revenue
    assert feb_row[1] == 138.00  # Feb revenue
    assert feb_row[2] == 400.00  # prev_month_revenue (LAG)
    assert feb_row[4] == -65.50  # mom_growth_pct: ((138 - 400) / 400) * 100

def test_query_02_top3_categories_by_state(mem_db):
    """Test Question 2: DENSE_RANK window function partitioned by state."""
    with open(config.sql_analysis_dir / "02_top3_categories_by_state.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    rows = mem_db.execute(sql).fetchall()
    assert len(rows) > 0
    # Every row must have rank <= 3
    for r in rows:
        state, rank, category, rev, orders, items = r
        assert rank <= 3

def test_query_03_7day_rolling_avg(mem_db):
    """Test Question 3: 7-day rolling window frame with calendar spine."""
    with open(config.sql_analysis_dir / "03_7day_rolling_order_count.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    rows = mem_db.execute(sql).fetchall()
    assert len(rows) > 0
    # Check that rolling_7day_avg_orders exists and is positive
    for r in rows:
        cal_date, count, rolling_avg = r
        assert rolling_avg >= 0.0

def test_query_04_repeat_purchase_rate(mem_db):
    """
    Test Question 4: Identity resolution using customer_unique_id.
    Synthetic setup:
      - cust_001 (ord_001) and cust_001_repeat (ord_003) share 'user_uuid_alpha' (2 orders).
      - cust_002 (ord_002) has 'user_uuid_beta' (1 order).
      - cust_003 (ord_004) is canceled.
    Denominator: 2 unique customers ('user_uuid_alpha', 'user_uuid_beta').
    Numerator: 1 repeat customer ('user_uuid_alpha').
    Repeat Rate = 50.00%.
    """
    with open(config.sql_analysis_dir / "04_repeat_purchase_rate.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    row = mem_db.execute(sql).fetchone()
    total_custs, single_custs, repeat_custs, rate_pct = row[0], row[1], row[2], row[3]
    assert total_custs == 2
    assert single_custs == 1
    assert repeat_custs == 1
    assert rate_pct == 50.00

def test_query_05_delivery_delay_vs_review(mem_db):
    """Test Question 5: Delay bucketing and review score averages."""
    with open(config.sql_analysis_dir / "05_delivery_delay_vs_review.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    rows = mem_db.execute(sql).fetchall()
    assert len(rows) > 0
    for r in rows:
        bucket, category, orders, share, delay, csat, pct5, pct1 = r
        assert csat >= 1.0 and csat <= 5.0
