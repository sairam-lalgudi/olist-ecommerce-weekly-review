"""Ingestion module: loads raw Olist CSV datasets into DuckDB raw schema with full validation."""
import time
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from typing import Dict, Any, Optional
import duckdb

from src.config import (
    config, logger, REQUIRED_TABLES, OPTIONAL_TABLES,
    MissingColumnError, MissingFileError
)

def get_connection(db_path: Optional[Path] = None) -> duckdb.DuckDBPyConnection:
    """Create or connect to the DuckDB analytical database."""
    target_path = str(db_path or config.duckdb_path)
    logger.info("Connecting to DuckDB at: %s", target_path)
    return duckdb.connect(target_path)

def validate_csv_columns(conn: duckdb.DuckDBPyConnection, table_name: str, csv_path: Path, required_cols: list) -> None:
    """Validate that required columns exist in the CSV before loading."""
    posix_path = csv_path.as_posix()
    # Read zero rows with header=true to inspect column names
    query = f"SELECT * FROM read_csv_auto('{posix_path}', header=true) LIMIT 0"
    col_names = [col[0] for col in conn.execute(query).description]
    
    missing = [c for c in required_cols if c not in col_names]
    if missing:
        msg = f"Table '{table_name}' from '{csv_path.name}' is missing required columns: {missing}"
        logger.error(msg)
        raise MissingColumnError(msg)

def ingest_raw_tables(conn: Optional[duckdb.DuckDBPyConnection] = None, data_dir: Optional[Path] = None) -> Dict[str, int]:
    """
    Ingest all validated CSVs into raw.* schema in DuckDB.
    Guarantees idempotency via deterministic CREATE OR REPLACE TABLE.
    """
    start_time = time.time()
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    effective_data_dir = data_dir or config.data_dir
    logger.info("Beginning raw ingestion from directory: %s", effective_data_dir)

    # Initialize raw schema
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw;")

    row_counts: Dict[str, int] = {}

    try:
        # 1. Ingest Required Tables
        for table_name, schema in REQUIRED_TABLES.items():
            csv_path = effective_data_dir / schema.filename
            if not csv_path.exists():
                raise MissingFileError(f"Required CSV not found: {csv_path}")

            validate_csv_columns(conn, table_name, csv_path, schema.required_columns)

            posix_path = csv_path.as_posix()
            t0 = time.time()
            logger.info("Ingesting required table raw.%s from %s...", table_name, schema.filename)
            
            # Idempotent table replacement
            conn.execute(f"""
                CREATE OR REPLACE TABLE raw.{table_name} AS 
                SELECT * FROM read_csv_auto('{posix_path}', header=true);
            """)
            
            count = conn.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()[0]
            row_counts[table_name] = count
            logger.info("Loaded raw.%s: %d rows (%.2fs)", table_name, count, time.time() - t0)

        # 2. Ingest Optional Tables
        for table_name, schema in OPTIONAL_TABLES.items():
            csv_path = effective_data_dir / schema.filename
            if csv_path.exists():
                validate_csv_columns(conn, table_name, csv_path, schema.required_columns)
                posix_path = csv_path.as_posix()
                t0 = time.time()
                logger.info("Ingesting optional table raw.%s from %s...", table_name, schema.filename)
                
                conn.execute(f"""
                    CREATE OR REPLACE TABLE raw.{table_name} AS 
                    SELECT * FROM read_csv_auto('{posix_path}', header=true);
                """)
                count = conn.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()[0]
                row_counts[table_name] = count
                logger.info("Loaded optional raw.%s: %d rows (%.2fs)", table_name, count, time.time() - t0)
            else:
                logger.warning("Optional file '%s' not present; raw.%s omitted.", schema.filename, table_name)

        total_elapsed = time.time() - start_time
        logger.info("Raw ingestion completed successfully across %d tables in %.2f seconds.", len(row_counts), total_elapsed)
        return row_counts

    finally:
        if should_close:
            conn.close()

if __name__ == "__main__":
    counts = ingest_raw_tables()
    print("Ingestion Summary:", counts)
