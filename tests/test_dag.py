"""Tests for the isolated Airflow DAG bonus deliverable."""
import pytest
from airflow.dags.olist_daily_wbr_dag import dag

def test_airflow_dag_structure():
    """Verify that the bonus Airflow DAG defines appropriate tasks and schedules."""
    assert dag.dag_id == "olist_ecommerce_daily_wbr_pipeline"
    assert dag.schedule_interval == "0 2 * * *"
    assert dag.catchup is False
    assert "duckdb" in dag.tags
    assert "ecommerce" in dag.tags
