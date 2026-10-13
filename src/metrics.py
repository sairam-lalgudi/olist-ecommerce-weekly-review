"""Metrics module: calculates North Star, supporting, and guardrail metrics from DuckDB."""
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional
import duckdb

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import config, logger

def compute_wbr_metrics(conn: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, Any]:
    """
    Computes all Weekly Business Review metrics using pure DuckDB SQL.
    Returns structured metric dictionary and exports JSON & CSV summaries.
    """
    should_close = False
    if conn is None:
        conn = duckdb.connect(str(config.duckdb_path))
        should_close = True

    logger.info("Computing Weekly Business Review (WBR) Core & Guardrail Metrics...")

    # 1. North Star: Net Marketplace GMV
    gmv_query = """
        SELECT 
            ROUND(SUM(gross_order_value), 2) AS net_gmv_brl,
            COUNT(DISTINCT order_id) AS total_valid_orders,
            ROUND(AVG(gross_order_value), 2) AS average_order_value_brl
        FROM mart.order_summary
        WHERE order_status NOT IN ('canceled', 'unavailable')
    """
    gmv_res = conn.execute(gmv_query).fetchone()
    net_gmv, total_orders, aov = gmv_res[0], gmv_res[1], gmv_res[2]

    # 2. Supporting Metric: Customer Repeat Purchase Rate
    repeat_query = """
        WITH cust_orders AS (
            SELECT customer_unique_id, COUNT(DISTINCT order_id) AS orders
            FROM mart.order_summary
            WHERE customer_unique_id IS NOT NULL 
              AND order_status NOT IN ('canceled', 'unavailable')
            GROUP BY customer_unique_id
        )
        SELECT 
            COUNT(*) AS total_customers,
            COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
            ROUND(100.0 * COUNT(*) FILTER (WHERE orders >= 2) / COUNT(*), 2) AS repeat_rate_pct
        FROM cust_orders
    """
    repeat_res = conn.execute(repeat_query).fetchone()
    total_customers, repeat_customers, repeat_rate = repeat_res[0], repeat_res[1], repeat_res[2]

    # 3. Supporting Metric: On-Time Delivery Rate
    delivery_query = """
        SELECT 
            COUNT(*) AS total_delivered,
            COUNT(*) FILTER (WHERE delivery_delay_days <= 0) AS on_time_orders,
            COUNT(*) FILTER (WHERE delivery_delay_days > 0) AS late_orders,
            COUNT(*) FILTER (WHERE delivery_delay_days > 7) AS severe_late_orders,
            ROUND(100.0 * COUNT(*) FILTER (WHERE delivery_delay_days <= 0) / COUNT(*), 2) AS on_time_rate_pct,
            ROUND(100.0 * COUNT(*) FILTER (WHERE delivery_delay_days > 7) / COUNT(*), 2) AS severe_late_rate_pct,
            ROUND(AVG(delivery_delay_days), 2) AS avg_delay_days,
            ROUND(AVG(delivery_duration_days), 2) AS avg_fulfillment_days
        FROM mart.order_summary
        WHERE order_status = 'delivered'
          AND delivered_ts IS NOT NULL
          AND estimated_ts IS NOT NULL
    """
    deliv_res = conn.execute(delivery_query).fetchone()
    (total_delivered, on_time_orders, late_orders, severe_late_orders, 
     on_time_rate, severe_late_rate, avg_delay_days, avg_fulfillment_days) = deliv_res

    # 4. Supporting Metric: Average Customer Satisfaction (CSAT)
    csat_query = """
        SELECT 
            ROUND(AVG(review_score), 2) AS avg_csat,
            COUNT(*) AS reviewed_orders,
            ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 5) / COUNT(*), 2) AS pct_5_star,
            ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 1) / COUNT(*), 2) AS pct_1_star
        FROM mart.order_summary
        WHERE review_score IS NOT NULL
    """
    csat_res = conn.execute(csat_query).fetchone()
    avg_csat, reviewed_orders, pct_5_star, pct_1_star = csat_res

    metrics = {
        "north_star_metric": {
            "name": "Net Marketplace GMV",
            "value": f"R$ {net_gmv:,.2f}",
            "numeric_value": net_gmv,
            "grain": "Aggregated completed orders",
            "formula": "SUM(item_price + freight_value) for order_status NOT IN ('canceled', 'unavailable')",
            "justification": "Primary indicator of platform commercial throughput and scale."
        },
        "average_order_value": {
            "name": "Average Order Value (AOV)",
            "value": f"R$ {aov:,.2f}",
            "numeric_value": aov,
            "formula": "Net GMV / Total Completed Orders"
        },
        "repeat_purchase_rate": {
            "name": "Customer Repeat Purchase Rate",
            "value": f"{repeat_rate:.2f}%",
            "numeric_value": repeat_rate,
            "numerator": repeat_customers,
            "denominator": total_customers,
            "grain": "Unique Customer (customer_unique_id)",
            "formula": "(Unique Customers with >=2 Orders / Total Unique Customers) * 100",
            "justification": "Gauges long-term retention and organic loyalty vs high single-order churn."
        },
        "on_time_delivery_rate": {
            "name": "On-Time Delivery Rate",
            "value": f"{on_time_rate:.2f}%",
            "numeric_value": on_time_rate,
            "numerator": on_time_orders,
            "denominator": total_delivered,
            "grain": "Delivered Order",
            "formula": "(Orders with delivery_delay_days <= 0 / Total Delivered Orders) * 100",
            "justification": "Core logistics SLA reflecting fulfillment against customer commitment date."
        },
        "severe_delay_rate": {
            "name": "Severe Delay Rate (>7 Days Late)",
            "value": f"{severe_late_rate:.2f}%",
            "numeric_value": severe_late_rate,
            "numerator": severe_late_orders,
            "denominator": total_delivered,
            "grain": "Delivered Order",
            "formula": "(Orders with delivery_delay_days > 7 / Total Delivered Orders) * 100",
            "justification": "Operational guardrail metric tracking the primary driver of 1-star reviews."
        },
        "average_csat": {
            "name": "Average Review Score (CSAT)",
            "value": f"{avg_csat:.2f} / 5.00",
            "numeric_value": avg_csat,
            "reviewed_orders": reviewed_orders,
            "pct_5_star": f"{pct_5_star:.2f}%",
            "pct_1_star": f"{pct_1_star:.2f}%",
            "grain": "Reviewed Order",
            "formula": "AVG(review_score) across all reviewed orders",
            "justification": "Direct voice-of-the-customer sentiment benchmark."
        }
    }

    # Save to JSON
    json_path = config.outputs_dir / "wbr_metrics_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Save to CSV
    csv_rows = [
        ("Net Marketplace GMV", f"R$ {net_gmv:,.2f}", "SUM(price + freight)", "Completed Orders"),
        ("Average Order Value (AOV)", f"R$ {aov:,.2f}", "Net GMV / Orders", "Completed Orders"),
        ("Repeat Purchase Rate", f"{repeat_rate:.2f}%", f"{repeat_customers:,} / {total_customers:,}", "customer_unique_id"),
        ("On-Time Delivery Rate", f"{on_time_rate:.2f}%", f"{on_time_orders:,} / {total_delivered:,}", "Delivered Orders"),
        ("Severe Delay Rate (>7d Late)", f"{severe_late_rate:.2f}%", f"{severe_late_orders:,} / {total_delivered:,}", "Delivered Orders"),
        ("Average Review Score (CSAT)", f"{avg_csat:.2f} / 5.00", "AVG(review_score)", "Reviewed Orders")
    ]
    csv_path = config.outputs_dir / "wbr_metrics_summary.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("metric_name,value,formula_or_ratio,grain\n")
        for m_name, val, formula, grain in csv_rows:
            f.write(f'"{m_name}","{val}","{formula}","{grain}"\n')

    logger.info("Computed WBR Metrics successfully: GMV=%s, Repeat=%s, On-Time=%s, CSAT=%s",
                metrics["north_star_metric"]["value"],
                metrics["repeat_purchase_rate"]["value"],
                metrics["on_time_delivery_rate"]["value"],
                metrics["average_csat"]["value"])

    if should_close:
        conn.close()

    return metrics

if __name__ == "__main__":
    res = compute_wbr_metrics()
    print(json.dumps(res, indent=2))
