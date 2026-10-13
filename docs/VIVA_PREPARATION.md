# Viva Defense & Examiner Q&A Guide
**Project:** Weekly Business Review for an E-commerce Marketplace  
**Dataset:** Brazilian E-Commerce Public Dataset by Olist (99,441 orders)  
**Database:** DuckDB (Local In-Process Vectorized OLAP)

---

## 1. High-Level Architecture & Medallion Design
### Q: Walk me through the architecture of your data pipeline.
**Answer:**  
Our pipeline follows an enterprise **Medallion Data Architecture** using **DuckDB**:
1. **Raw Layer (`raw.*`)**: Direct schema-validated ingestion of raw CSV files. We validate that all mandatory files and columns exist before loading. Loading is idempotent via `CREATE OR REPLACE TABLE`.
2. **Staging Layer (`staging.*`)**: Type-coerced and sanitized models. Dates are parsed to timestamps (`TRY_CAST`), strings are trimmed, monetary amounts are rounded to 2 decimals, and empty strings are converted to `NULL`.
3. **Curated Mart Layer (`mart.order_summary`)**: An order-grain dimensional mart with **exactly one row per order** (`order_id`). Pre-aggregates line items, payments, and reviews in separate CTEs before joining to prevent Cartesian fanout.
4. **Audit Layer (`audit.quality_results`)**: Executes 7 pure SQL data quality assertions with a hard gate that halts the pipeline on critical failures.
5. **Analytical SQL Suite (Part C)**: Pure DuckDB SQL queries utilizing window functions (`LAG`, `DENSE_RANK`), rolling frames, and calendar spines.
6. **Reporting & PDF Layer**: Automated generation of Matplotlib visualizations and a 5-page board-ready PDF executive report using ReportLab.

---

## 2. Ingestion & Invariants (Part A)
### Q: Why did you choose DuckDB over PostgreSQL or Pandas?
**Answer:**  
1. **DuckDB vs PostgreSQL:** DuckDB is an in-process, vectorized columnar analytical database. It requires **zero external server setup or Docker containers**, runs embedded directly in Python, and executes analytical queries orders of magnitude faster on columnar data than traditional row-oriented transactional databases like PostgreSQL.
2. **DuckDB vs Pandas:** Big Data engineering requires SQL-first processing. Staging and joining data in pure SQL inside DuckDB leverages columnar execution, vectorized SIMD execution, and avoids the high memory footprint of Python objects. Pandas is strictly restricted to chart plotting and report formatting.

### Q: What is the "1-to-Many Join Fanout" problem and how did you prevent it?
**Answer:**  
An order can have multiple line items, multiple payment installments/methods, and multiple reviews:
- If we naively join `orders` to `order_items` (1:N) and then join to `payments` (1:M), DuckDB creates an `N × M` Cartesian product!
- **Example:** An order with 2 items and 2 payments would multiply into 4 rows. Summing prices or payment values across these rows would artificially double or triple the order revenue!
- **Our Solution:** We pre-aggregate each child entity in separate Common Table Expressions (CTEs):
  ```sql
  WITH item_agg AS (
      SELECT order_id, SUM(price) AS item_total, SUM(freight_value) AS freight_total, COUNT(*) AS item_count
      FROM staging.order_items GROUP BY order_id
  ),
  payment_agg AS (
      SELECT order_id, SUM(payment_value) AS payment_total, COUNT(*) AS payment_count
      FROM staging.payments GROUP BY order_id
  ),
  review_agg AS (
      SELECT order_id, AVG(review_score) AS review_score, COUNT(*) AS review_count
      FROM staging.reviews GROUP BY order_id
  )
  SELECT ...
  FROM staging.orders o
  LEFT JOIN item_agg i ON o.order_id = i.order_id
  LEFT JOIN payment_agg p ON o.order_id = p.order_id
  LEFT JOIN review_agg r ON o.order_id = r.order_id;
  ```
- This guarantees the **one-row-per-order invariant** (`COUNT(*) = COUNT(DISTINCT order_id) = 99,441`).

### Q: How did you ensure pipeline idempotency?
**Answer:**  
An idempotent pipeline produces the exact same state regardless of how many times it is executed. We achieve this by using deterministic `CREATE OR REPLACE TABLE` statements for all raw, staging, and mart tables. Re-running the pipeline replaces the tables cleanly rather than appending duplicate rows or accumulating financial totals.

---

## 3. Data Quality & Governance (Part B)
### Q: What data quality checks did you implement, and what were the actual results?
**Answer:**  
We implemented 7 SQL assertions:
1. `null_or_duplicate_order_id` (CRITICAL): **0 failing rows** (PASS). Primary key integrity confirmed.
2. `delivered_before_purchase` (CRITICAL): **0 failing rows** (PASS). Chronological impossibility check.
3. `payment_vs_items_freight` (INFORMATIONAL): **260 failing rows** (FLAG). Reconciles order gross total vs payment gateway total within R$ 0.05.
4. `orders_without_customer` (CRITICAL): **0 failing rows** (PASS). Referential integrity between orders and customers.
5. `invalid_review_scores` (INFORMATIONAL): **0 failing rows** (PASS). Verifies 1–5 rating bounds.
6. `negative_item_prices` (CRITICAL): **0 failing rows** (PASS). Verifies economic validity of prices and freight.
7. `delivered_before_carrier` (INFORMATIONAL): **23 failing rows** (FLAG). Logistics carrier scan chronology.

### Q: Why did 260 rows fail payment reconciliation, and why didn't you drop them?
**Answer:**  
In Brazilian e-commerce, payment values often deviate from `item_price + freight_value` due to legitimate domain business practices:
1. **Credit card installment financing (*parcelamento*):** Extended installments (e.g., 10x or 12x) include financing interest charged by credit card gateways, making payment total higher than the base item sum (e.g., Order `ce6d150fb29ada17d2082f4847107665`: expected R$ 1,403.66, paid R$ 1,586.47).
2. **Promotional vouchers and discounts:** Customers apply marketplace discount coupons, making payment total lower.
**Governance Decision:** In production Big Data engineering, dropping these records would corrupt the financial ledger. We preserve the raw records immutably and flag them in the curated mart with `has_payment_discrepancy = TRUE` for audit tracking.

---

## 4. Analytical SQL (Part C)
### Q: Explain the difference between `customer_id` and `customer_unique_id` in Question 4.
**Answer:**  
- `customer_id` is a transaction-specific surrogate key generated anew for every single order. If a person places 5 orders, they receive 5 different `customer_id` values!
- `customer_unique_id` represents the true persistent real-world individual.
- **Repeat Purchase Rate:**
  - **Denominator:** Total unique customers = `COUNT(DISTINCT customer_unique_id)` = **94,990**.
  - **Numerator:** Unique customers with $\ge 2$ distinct orders = `COUNT(DISTINCT customer_unique_id)` with `order_count >= 2` = **2,888**.
  - **Repeat Rate:** $\frac{2,888}{94,990} \times 100 = \mathbf{3.04\%}$.

### Q: How did you implement Question 3 to include calendar dates with zero orders?
**Answer:**  
A simple `GROUP BY order_date` skips dates where no sales occurred. To include zero-order days:
1. We compute `MIN(purchase_ts)` and `MAX(purchase_ts)`.
2. We generate a continuous daily calendar spine using DuckDB's `UNNEST(range(min_date, max_date + INTERVAL 1 DAY, INTERVAL 1 DAY))`.
3. We `LEFT JOIN` the calendar spine to the daily order count aggregation, using `COALESCE(daily_order_count, 0)`.
4. We apply a 7-day rolling window frame: `AVG(daily_order_count) OVER (ORDER BY calendar_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)`.
5. This revealed **140 days with zero orders** (mainly during late 2016 pre-launch) and a record peak on **November 24, 2017 (1,176 orders on Black Friday)**.

### Q: What is the "Delivery Penalty Cliff" discovered in Question 5?
**Answer:**  
When delivery is early or on-time (91.89% of orders), customers award an average review score of **4.29 / 5.00** (63% 5-star, 7% 1-star).  
However, when delivery is delayed:
- **1 to 7 days late:** Average review drops to **3.18 / 5.00**, with 1-star reviews jumping to **29.57%**.
- **> 7 days late:** Average review collapses to **1.73 / 5.00**, with **68.66% awarding 1-star reviews**!  
This steep drop is the **Delivery Penalty Cliff**.

---

## 5. Executive Storytelling & Recommendations (Part D)
### Q: What is the core business recommendation in your VP memo?
**Answer:**  
Olist suffers from a **3.04% repeat purchase rate** (96.96% one-time buyers). The marketplace is pouring acquisition spend into a leaky bucket because late deliveries destroy first-time customer trust.  
**Actionable Recommendation:**
1. Establish a **Regional Fulfillment Hub Program** in São Paulo and Rio de Janeiro (the source of >65% GMV) for top categories (*bed_bath_table*, *health_beauty*).
2. Enforce a **48-hour merchant dispatch SLA** with search algorithm deprioritization for offending sellers.
3. Launch automated **Proactive Delay Remediation**: issue an immediate R$ 20 repeat-purchase voucher whenever shipping telemetry detects an unavoidable postal delay.
4. Measure success via a **90-day randomized A/B trial** targeting a repeat purchase rate increase from 3.04% to 5.00%.
