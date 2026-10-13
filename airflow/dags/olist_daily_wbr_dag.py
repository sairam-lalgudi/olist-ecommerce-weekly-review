"""Apache Airflow DAG: Daily orchestration of the Olist E-Commerce Weekly Business Review pipeline.

Bonus Deliverable (5 Marks):
This DAG is strictly isolated. The core pipeline operates independently of Airflow.
Scheduled daily to ingest delta extracts, transform staging models, enforce SQL quality gates,
execute Part C analytical queries, calculate WBR metrics, and compile executive PDF packs.
"""
from datetime import datetime, timedelta
import os
import sys

# Add project root to sys.path so Airflow workers can locate src modules
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.operators.empty import EmptyOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    # Graceful fallback mock classes for testing when Airflow is not installed locally
    AIRFLOW_AVAILABLE = False
    class DAG:
        def __init__(self, dag_id, default_args=None, schedule_interval=None, start_date=None, catchup=False, tags=None, **kwargs):
            self.dag_id = dag_id
            self.default_args = default_args or {}
            self.schedule_interval = schedule_interval
            self.start_date = start_date
            self.catchup = catchup
            self.tags = tags or []
            self.extra_kwargs = kwargs
            self.tasks = []

    class BaseOperator:
        def __init__(self, task_id, **kwargs):
            self.task_id = task_id
            self.upstream = []
            self.downstream = []

        def __rshift__(self, other):
            if isinstance(other, list):
                for o in other:
                    self.downstream.append(o)
                    o.upstream.append(self)
            else:
                self.downstream.append(other)
                other.upstream.append(self)
            return other

    class PythonOperator(BaseOperator):
        def __init__(self, task_id, python_callable, **kwargs):
            super().__init__(task_id, **kwargs)
            self.python_callable = python_callable

    class EmptyOperator(BaseOperator):
        pass

def task_validate_inputs(**kwargs):
    """Task 1: Validate existence and schemas of raw CSV extracts."""
    from src.config import config
    config.validate_inputs()
    return "Inputs validated successfully."

def task_ingest_raw(**kwargs):
    """Task 2: Ingest raw CSV files into DuckDB raw.* schema."""
    from src.ingest import ingest_raw_tables
    counts = ingest_raw_tables()
    return counts

def task_transform_staging_and_mart(**kwargs):
    """Task 3: Build cleaned staging tables and one-row-per-order mart."""
    from src.transform import run_transformations
    res = run_transformations()
    return res

def task_run_quality_gate(**kwargs):
    """Task 4: Execute SQL assertions and enforce data quality gate."""
    from src.quality_checks import run_quality_checks
    results = run_quality_checks()
    return f"Passed {len(results)} quality checks."

def task_execute_part_c_analytics(**kwargs):
    """Task 5: Execute all 5 Part C analytical queries into analysis.* and CSVs."""
    from src.run_queries import execute_analytical_queries
    exported = execute_analytical_queries()
    return exported

def task_metrics_and_reporting(**kwargs):
    """Task 6: Compute WBR metrics, render Matplotlib charts, and generate 5-page PDF report."""
    from src.metrics import compute_wbr_metrics
    from src.charts import generate_all_charts
    from src.build_report import build_pdf_report

    compute_wbr_metrics()
    generate_all_charts()
    pdf_path = build_pdf_report()
    return f"Report generated at {pdf_path}"

default_args = {
    "owner": "data_engineering_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Define DAG scheduled daily at 02:00 AM UTC
dag = DAG(
    dag_id="olist_ecommerce_daily_wbr_pipeline",
    default_args=default_args,
    description="Daily production batch orchestration for Olist WBR and Mart builds",
    schedule_interval="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ecommerce", "olist", "duckdb", "wbr", "bigdata"],
)

if True:
    start_task = EmptyOperator(task_id="start_pipeline")
    end_task = EmptyOperator(task_id="end_pipeline")

    t1_validate = PythonOperator(
        task_id="validate_raw_inputs",
        python_callable=task_validate_inputs,
    )

    t2_ingest = PythonOperator(
        task_id="ingest_raw_tables",
        python_callable=task_ingest_raw,
    )

    t3_transform = PythonOperator(
        task_id="build_staging_and_mart",
        python_callable=task_transform_staging_and_mart,
    )

    t4_quality_gate = PythonOperator(
        task_id="enforce_sql_quality_gate",
        python_callable=task_run_quality_gate,
    )

    t5_analytics = PythonOperator(
        task_id="execute_part_c_analytics",
        python_callable=task_execute_part_c_analytics,
    )

    t6_reporting = PythonOperator(
        task_id="generate_metrics_charts_and_pdf",
        python_callable=task_metrics_and_reporting,
    )

    # Establish task dependency pipeline graph
    start_task >> t1_validate >> t2_ingest >> t3_transform >> t4_quality_gate >> t5_analytics >> t6_reporting >> end_task
