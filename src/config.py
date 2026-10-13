"""Pipeline configuration, schema registries, and path resolution for Olist WBR."""
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Set up standard logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("olist_wbr")

class PipelineError(Exception):
    """Base exception for Olist pipeline operations."""
    pass

class MissingFileError(PipelineError):
    """Raised when a mandatory input CSV file is not found."""
    pass

class MissingColumnError(PipelineError):
    """Raised when a required column is absent from an input dataset."""
    pass

class DataQualityError(PipelineError):
    """Raised when one or more critical data quality checks fail the audit gate."""
    pass

@dataclass(frozen=True)
class TableSchema:
    filename: str
    required_columns: List[str]
    optional_columns: List[str] = field(default_factory=list)
    description: str = ""

# Definition of all required tables and schemas
REQUIRED_TABLES: Dict[str, TableSchema] = {
    "orders": TableSchema(
        filename="olist_orders_dataset.csv",
        required_columns=[
            "order_id", "customer_id", "order_status",
            "order_purchase_timestamp", "order_estimated_delivery_date"
        ],
        optional_columns=[
            "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date"
        ],
        description="Core orders table tracking order lifecycle states and timestamps"
    ),
    "order_items": TableSchema(
        filename="olist_order_items_dataset.csv",
        required_columns=[
            "order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"
        ],
        optional_columns=["shipping_limit_date"],
        description="Line-item details per order with prices and freight charges"
    ),
    "payments": TableSchema(
        filename="olist_order_payments_dataset.csv",
        required_columns=[
            "order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"
        ],
        description="Payment transactions per order (credit card, boleto, voucher, debit)"
    ),
    "reviews": TableSchema(
        filename="olist_order_reviews_dataset.csv",
        required_columns=[
            "review_id", "order_id", "review_score"
        ],
        optional_columns=[
            "review_comment_title", "review_comment_message", "review_creation_date", "review_answer_timestamp"
        ],
        description="Customer satisfaction ratings (1 to 5) and feedback timestamps"
    ),
    "customers": TableSchema(
        filename="olist_customers_dataset.csv",
        required_columns=[
            "customer_id", "customer_unique_id", "customer_state"
        ],
        optional_columns=["customer_zip_code_prefix", "customer_city"],
        description="Customer demographic data mapping transaction IDs to persistent identity"
    ),
    "products": TableSchema(
        filename="olist_products_dataset.csv",
        required_columns=[
            "product_id", "product_category_name"
        ],
        optional_columns=[
            "product_name_lenght", "product_description_lenght", "product_photos_qty",
            "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"
        ],
        description="Product catalog metadata and categorization"
    ),
}

# Optional supplementary tables
OPTIONAL_TABLES: Dict[str, TableSchema] = {
    "sellers": TableSchema(
        filename="olist_sellers_dataset.csv",
        required_columns=["seller_id", "seller_state"],
        optional_columns=["seller_zip_code_prefix", "seller_city"],
        description="Merchant metadata"
    ),
    "geolocation": TableSchema(
        filename="olist_geolocation_dataset.csv",
        required_columns=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
        optional_columns=["geolocation_city", "geolocation_state"],
        description="Brazilian zip code geo-coordinates"
    ),
    "category_translation": TableSchema(
        filename="product_category_name_translation.csv",
        required_columns=["product_category_name", "product_category_name_english"],
        description="Portuguese to English translation of product category names"
    ),
}

@dataclass
class Config:
    base_dir: Path = field(default_factory=lambda: Path(os.getenv("PROJECT_DIR", ".")).resolve())
    data_dir: Path = field(init=False)
    duckdb_path: Path = field(init=False)
    outputs_dir: Path = field(init=False)
    reports_dir: Path = field(init=False)
    charts_dir: Path = field(init=False)
    sql_checks_dir: Path = field(init=False)
    sql_analysis_dir: Path = field(init=False)
    payment_tolerance: float = 0.05  # Monetary tolerance in BRL for payment vs items+freight

    def __post_init__(self):
        self.data_dir = Path(os.getenv("DATA_DIR", self.base_dir / "data" / "raw")).resolve()
        db_path = os.getenv("DUCKDB_PATH", str(self.base_dir / "data" / "olist_dw.duckdb"))
        self.duckdb_path = Path(db_path).resolve()
        self.outputs_dir = Path(os.getenv("OUTPUT_DIR", self.base_dir / "outputs")).resolve()
        self.reports_dir = Path(os.getenv("REPORTS_DIR", self.base_dir / "reports")).resolve()
        self.charts_dir = Path(os.getenv("CHARTS_DIR", self.reports_dir / "charts")).resolve()
        self.sql_checks_dir = (self.base_dir / "sql" / "checks").resolve()
        self.sql_analysis_dir = (self.base_dir / "sql" / "analysis").resolve()

        # Ensure directories exist
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_inputs(self) -> Dict[str, Path]:
        """Validate presence of all required input CSV files and return resolved paths."""
        resolved: Dict[str, Path] = {}
        missing: List[str] = []

        for table_name, schema in REQUIRED_TABLES.items():
            csv_path = self.data_dir / schema.filename
            if not csv_path.exists():
                missing.append(f"{schema.filename} (for table '{table_name}')")
            else:
                resolved[table_name] = csv_path

        if missing:
            msg = (
                f"Missing required CSV dataset files in '{self.data_dir}':\n"
                + "\n".join(f"  - {m}" for m in missing)
                + "\n\nPlease download the Olist Brazilian E-Commerce dataset from Kaggle "
                "and place the CSV files in 'data/raw/'."
            )
            logger.error(msg)
            raise MissingFileError(msg)

        # Check optional files
        for table_name, schema in OPTIONAL_TABLES.items():
            csv_path = self.data_dir / schema.filename
            if csv_path.exists():
                resolved[table_name] = csv_path
            else:
                logger.info("Optional file '%s' not present; skipping table '%s'", schema.filename, table_name)

        return resolved

# Singleton config instance
config = Config()
