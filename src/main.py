"""Unified pipeline driver: orchestrates end-to-end ingestion, mart building, quality gates, analytics, charts, and PDF reporting."""
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import config, logger, DataQualityError, PipelineError
from src.ingest import ingest_raw_tables
from src.transform import run_transformations
from src.quality_checks import run_quality_checks
from src.run_queries import execute_analytical_queries
from src.metrics import compute_wbr_metrics
from src.charts import generate_all_charts
from src.build_report import build_pdf_report

def run_pipeline() -> None:
    """Execute the complete end-to-end analytical pipeline."""
    total_start = time.time()
    logger.info("=" * 80)
    logger.info("STARTING OLIST E-COMMERCE WEEKLY BUSINESS REVIEW PIPELINE")
    logger.info("=" * 80)

    try:
        # Phase 1: Input Validation
        logger.info("[PHASE 1/7] Validating input dataset CSV files...")
        resolved_inputs = config.validate_inputs()
        logger.info("Validated %d input datasets in %s.", len(resolved_inputs), config.data_dir)

        # Phase 2: Raw Ingestion
        logger.info("[PHASE 2/7] Ingesting CSV files into DuckDB raw schema...")
        raw_counts = ingest_raw_tables()

        # Phase 3: Staging Models and Mart Creation
        logger.info("[PHASE 3/7] Building staging tables and curated one-row-per-order mart...")
        transform_res = run_transformations()

        # Phase 4: Data Quality Checks & Quality Gate
        logger.info("[PHASE 4/7] Executing Part B SQL Data Quality assertions...")
        dq_results = run_quality_checks()

        # Phase 5: Part C Analytical Queries Execution
        logger.info("[PHASE 5/7] Executing Part C Analytical SQL suite...")
        exported_queries = execute_analytical_queries()

        # Phase 6: WBR Metrics & Visualizations
        logger.info("[PHASE 6/7] Computing WBR metrics and rendering Matplotlib charts...")
        metrics = compute_wbr_metrics()
        charts = generate_all_charts()

        # Phase 7: 5-Page PDF Executive Report Generation
        logger.info("[PHASE 7/7] Compiling 5-page executive PDF report...")
        pdf_path = build_pdf_report()

        total_elapsed = time.time() - total_start
        logger.info("=" * 80)
        logger.info("PIPELINE EXECUTION COMPLETED SUCCESSFULLY IN %.2f SECONDS", total_elapsed)
        logger.info("Summary of Deliverables:")
        logger.info("  - Analytical DB:      %s", config.duckdb_path)
        logger.info("  - Curated Mart Rows:  %d (mart.order_summary)", transform_res["mart_rows"])
        logger.info("  - Data Quality:       %d checks evaluated (Gate Passed)", len(dq_results))
        logger.info("  - Exported CSVs:      %d analytical tables in %s", len(exported_queries), config.outputs_dir)
        logger.info("  - Generated Charts:   %d figures in %s", len(charts), config.charts_dir)
        logger.info("  - Executive PDF Pack: %s", pdf_path)
        logger.info("=" * 80)

    except DataQualityError as exc:
        logger.error("PIPELINE HALTED BY DATA QUALITY GATE: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("FATAL PIPELINE FAILURE: %s", exc)
        sys.exit(2)

if __name__ == "__main__":
    run_pipeline()
