"""Data quality engine: executes pure SQL assertions, logs to audit schema, and enforces quality gates."""
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import duckdb

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import config, logger, DataQualityError

def run_quality_checks(conn: Optional[duckdb.DuckDBPyConnection] = None) -> List[Dict[str, Any]]:
    """
    Execute all SQL checks defined in sql/checks/data_quality_checks.sql,
    persisting results to audit.quality_results and evaluating the quality gate.
    """
    should_close = False
    if conn is None:
        conn = duckdb.connect(str(config.duckdb_path))
        should_close = True

    logger.info("Initializing audit schema and executing Part B SQL Data Quality Checks...")
    conn.execute("CREATE SCHEMA IF NOT EXISTS audit;")
    
    # Audit table stores historical runs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit.quality_results (
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            check_name VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            failed_rows BIGINT NOT NULL,
            status VARCHAR NOT NULL,
            remediation VARCHAR NOT NULL
        );
    """)

    sql_path = config.sql_checks_dir / "data_quality_checks.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL checks file not found at: {sql_path}")

    with open(sql_path, "r", encoding="utf-8") as f:
        query_sql = f.read()

    rows = conn.execute(query_sql).fetchall()

    results: List[Dict[str, Any]] = []
    critical_failures: List[str] = []

    logger.info("=" * 90)
    logger.info(f"{'CHECK NAME':<38} | {'SEVERITY':<12} | {'FAILED':<8} | {'STATUS':<6}")
    logger.info("-" * 90)

    from datetime import datetime, timezone
    run_ts = datetime.now(timezone.utc)

    for check_name, desc, severity, failed_rows, remediation in rows:
        failed_count = int(failed_rows)
        if failed_count == 0:
            status = "PASS"
        elif severity == "CRITICAL":
            status = "FAIL"
            critical_failures.append(f"{check_name} ({failed_count} failing rows)")
        else:
            status = "FLAG"

        logger.info(f"{check_name:<38} | {severity:<12} | {failed_count:<8} | {status:<6}")

        record = {
            "check_name": check_name,
            "description": desc,
            "severity": severity,
            "failed_rows": failed_count,
            "status": status,
            "remediation": remediation
        }
        results.append(record)

        # Log into audit table with unified run timestamp
        conn.execute("""
            INSERT INTO audit.quality_results (run_at, check_name, description, severity, failed_rows, status, remediation)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, [run_ts, check_name, desc, severity, failed_count, status, remediation])

    logger.info("=" * 90)

    # Export to outputs directory
    out_csv = config.outputs_dir / "quality_check_results.csv"
    logger.info("Exporting audit results to: %s", out_csv)
    
    conn.execute(f"""
        COPY (
            SELECT check_name, severity, failed_rows, status, description, remediation
            FROM audit.quality_results
            WHERE run_at = ?
            ORDER BY severity DESC, failed_rows DESC
        ) TO '{out_csv.as_posix()}' (HEADER, DELIMITER ',');
    """, [run_ts])

    if critical_failures:
        error_msg = (
            f"Quality Gate Failed: {len(critical_failures)} critical data check(s) violated:\n"
            + "\n".join(f"  - {f}" for f in critical_failures)
        )
        logger.error(error_msg)
        if should_close:
            conn.close()
        raise DataQualityError(error_msg)

    logger.info("Data Quality Gate PASSED. All critical checks verified successfully.")
    
    if should_close:
        conn.close()

    return results

if __name__ == "__main__":
    try:
        run_quality_checks()
    except DataQualityError as exc:
        logger.error("PIPELINE HALTED: %s", exc)
        sys.exit(1)
