"""Query execution engine: runs all Part C analytical SQL queries, stores in analysis schema, and exports CSVs."""
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
import duckdb

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import config, logger

QUERY_FILES = [
    ("01_monthly_revenue_growth.sql", "mom_revenue_growth"),
    ("02_top3_categories_by_state.sql", "top3_categories_by_state"),
    ("03_7day_rolling_order_count.sql", "rolling_7day_order_count"),
    ("04_repeat_purchase_rate.sql", "repeat_purchase_rate"),
    ("05_delivery_delay_vs_review.sql", "delivery_delay_vs_review"),
]

def execute_analytical_queries(conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, str]:
    """
    Executes each analytical SQL query against DuckDB,
    persists as analysis.<table_name> in DuckDB,
    and exports exact CSV outputs to the outputs/ directory.
    """
    should_close = False
    if conn is None:
        conn = duckdb.connect(str(config.duckdb_path))
        should_close = True

    logger.info("Executing Part C Analytical SQL Suite...")
    conn.execute("CREATE SCHEMA IF NOT EXISTS analysis;")

    exported_files: Dict[str, str] = {}

    try:
        for filename, table_name in QUERY_FILES:
            sql_file = config.sql_analysis_dir / filename
            if not sql_file.exists():
                raise FileNotFoundError(f"Part C SQL file not found: {sql_file}")

            with open(sql_file, "r", encoding="utf-8") as f:
                sql_query = f.read()

            t0 = time.time()
            logger.info("Running query %s -> analysis.%s...", filename, table_name)
            
            # Persist as analytical table
            conn.execute(f"CREATE OR REPLACE TABLE analysis.{table_name} AS {sql_query}")
            
            row_count = conn.execute(f"SELECT COUNT(*) FROM analysis.{table_name}").fetchone()[0]
            
            # Export CSV
            out_csv = config.outputs_dir / f"{Path(filename).stem}.csv"
            conn.execute(f"COPY analysis.{table_name} TO '{out_csv.as_posix()}' (HEADER, DELIMITER ',');")
            
            elapsed = time.time() - t0
            logger.info("Query %s finished: %d rows written to %s (%.2fs)", filename, row_count, out_csv.name, elapsed)
            exported_files[filename] = str(out_csv)

        logger.info("All 5 Part C analytical queries executed and exported successfully.")
        return exported_files

    finally:
        if should_close:
            conn.close()

if __name__ == "__main__":
    results = execute_analytical_queries()
    print("Exported Analysis Files:", results)
