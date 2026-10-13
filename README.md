# Weekly Business Review for an E-commerce Marketplace
**Course Assignment: Big Data Analytics & Engineering**  
**Dataset Source:** [Brazilian E-Commerce Public Dataset by Olist (Kaggle)](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

---

## 1. Project Overview & Architecture
This project delivers a complete, reproducible end-to-end Big Data analytical engineering pipeline and executive Weekly Business Review (WBR) reporting pack for the Olist marketplace.

The pipeline is built on an enterprise medallion architecture:
1. **Raw Layer (`raw.*`)**: Direct schema-validated ingestion of raw CSV extracts into local analytical database tables.
2. **Staging Layer (`staging.*`)**: Type-coerced, sanitized data models with validated primary keys and normalized null timestamps.
3. **Data Mart Layer (`mart.*`)**: Curated, denormalized dimensional and aggregate marts. The core order mart guarantees an invariant of **exactly one row per order** by pre-aggregating line items, payments, and reviews before joining.
4. **Data Quality Gate (`audit.*`)**: Automated suite of SQL assertions enforcing referential integrity, financial reconciliation tolerances, and chronological sequences before analytics can run.
5. **Analytical SQL Suite (Part C)**: Pure DuckDB SQL queries utilizing modern analytical patterns (`LAG`, `DENSE_RANK`, rolling window frames, CTEs, and calendar spine generation).
6. **Executive Storytelling & Reporting (Part D & PDF)**: Metric calculation engine, production visualizations (Matplotlib), and a board-ready ReportLab 5-page PDF report.
7. **Orchestration (Bonus)**: Isolated daily Apache Airflow DAG demonstrating production batch scheduling.

---

## 2. Technology Stack & Design Decisions
- **Analytical Database:** **DuckDB** — In-process, vectorized SQL OLAP engine. Provides enterprise-grade SQL-2016 support without requiring external server setup (e.g. Postgres Docker containers).
- **Core Pipeline:** Python 3.11+ with robust logging, granular exception hierarchies, and transactional DDL/DML.
- **Data Quality & Analysis:** Pure SQL. **Zero pandas transformations are used for Part B checks or Part C analytical queries**, adhering strictly to Big Data engineering principles.
- **Reporting & Visualizations:** `matplotlib` for publication-quality charts and `reportlab` for generating the 5-page PDF executive pack.
- **Testing:** `pytest` test suite covering schema validation, idempotency, mart uniqueness invariants, and SQL queries on synthetic fixtures.

---

## 3. Dataset Setup & Acquisition
The pipeline requires the 9 official Olist dataset CSV files placed in the `data/raw/` directory:
- `olist_orders_dataset.csv` (Required)
- `olist_order_items_dataset.csv` (Required)
- `olist_order_payments_dataset.csv` (Required)
- `olist_order_reviews_dataset.csv` (Required)
- `olist_customers_dataset.csv` (Required)
- `olist_products_dataset.csv` (Required)
- `olist_sellers_dataset.csv` (Optional)
- `olist_geolocation_dataset.csv` (Optional)
- `product_category_name_translation.csv` (Optional, used for Portuguese-to-English category translation)

### How to Download
Option A: **Manual Kaggle Download**
1. Visit [Olist Brazilian E-Commerce on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
2. Download the archive and extract all CSV files into `data/raw/`.

Option B: **Using Kaggle CLI / Python**
```bash
python -c "import kagglehub; kagglehub.dataset_download('olistbr/brazilian-ecommerce')"
```
Copy the extracted files from your local Kaggle cache into `data/raw/`.

---

## 4. Quickstart: Reproducing the Entire Pipeline
### Step 1: Set up Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
cp .env.example .env
```

### Step 3: Run Full Pipeline
To execute ingestion, staging, mart builds, data quality gates, Part C queries, metric exports, charts, and the final PDF report in one command:
```bash
python src/main.py
```

### Step 4: Run Test Suite
```bash
pytest -v
```

---

## 5. Repository Directory Layout
```
olist-ecommerce-weekly-review/
├── README.md                          # Project documentation and reproduction guide
├── requirements.txt                   # Pinned project dependencies
├── .gitignore                         # Git exclusion rules for large datasets and DBs
├── .env.example                       # Template environment configuration
├── config/                            # Pipeline configuration schemas and tolerances
├── data/
│   └── raw/                           # Raw Olist CSV data directory (git-ignored)
├── sql/
│   ├── checks/                        # Part B SQL Data Quality Check queries
│   │   └── data_quality_checks.sql
│   └── analysis/                      # Part C SQL Analytical queries
│       ├── 01_monthly_revenue_growth.sql
│       ├── 02_top3_categories_by_state.sql
│       ├── 03_7day_rolling_order_count.sql
│       ├── 04_repeat_purchase_rate.sql
│       └── 05_delivery_delay_vs_review.sql
├── src/
│   ├── __init__.py
│   ├── config.py                      # Path resolver, schema registry, and tolerances
│   ├── ingest.py                      # Raw CSV schema validation and DuckDB ingestion
│   ├── transform.py                   # Staging models and one-row-per-order mart build
│   ├── quality_checks.py              # Part B SQL Quality Gate execution engine
│   ├── run_queries.py                 # Part C SQL runner and CSV result exporter
│   ├── metrics.py                     # WBR North Star and supporting metrics calculator
│   ├── charts.py                      # Matplotlib visualization suite
│   ├── build_report.py                # 5-Page ReportLab PDF publication generator
│   └── main.py                        # Unified end-to-end pipeline driver
├── tests/                             # Pytest suite with synthetic fixtures
│   ├── conftest.py
│   ├── test_ingest.py
│   ├── test_transform.py
│   ├── test_quality_checks.py
│   └── test_sql_queries.py
├── reports/
│   ├── charts/                        # Generated PNG charts
│   └── weekly_business_review.pdf     # Final compiled 5-page PDF report
├── outputs/                           # Exported CSV tables for Part C queries & metrics
├── airflow/
│   └── dags/                          # Bonus isolated Airflow daily DAG
└── docs/                              # Data dictionary, Viva Q&A, and metric definitions
```
