-- ==============================================================================
-- PART B: DATA QUALITY CHECKS SUITE
-- Database: DuckDB (Schema: staging, audit)
-- Evaluates primary keys, chronological sequences, referential integrity,
-- financial reconciliation, review score bounds, and postal tracking logic.
-- ==============================================================================

-- Check 1: Null or duplicate order_id in staging.orders (CRITICAL)
-- Invariant: Primary key must be strictly unique and non-null.
SELECT 
    'check_1_null_or_duplicate_order_id' AS check_name,
    'Critical: Ensures primary key uniqueness and non-null constraint on orders' AS description,
    'CRITICAL' AS severity,
    COUNT(*) AS failed_rows,
    'Stop pipeline immediately; inspect source extraction for duplicate order keys' AS remediation
FROM (
    SELECT order_id FROM staging.orders WHERE order_id IS NULL
    UNION ALL
    SELECT order_id FROM staging.orders GROUP BY order_id HAVING COUNT(*) > 1
) sub_pk

UNION ALL

-- Check 2: Delivered timestamp earlier than purchase timestamp (CRITICAL)
-- Invariant: Orders cannot be physically delivered before they are placed.
SELECT 
    'check_2_delivered_before_purchase' AS check_name,
    'Critical: Chronological integrity checking if delivery predates order purchase' AS description,
    'CRITICAL' AS severity,
    COUNT(*) AS failed_rows,
    'Stop pipeline; flag upstream event stream or time synchronization drift' AS remediation
FROM staging.orders
WHERE delivered_ts IS NOT NULL 
  AND purchase_ts IS NOT NULL 
  AND delivered_ts < purchase_ts

UNION ALL

-- Check 3: Payment total compared with item price plus freight (INFORMATIONAL / FLAG)
-- Tolerance: ABS((item_total + freight_total) - payment_total) > 0.05 BRL
-- Invariant: E-commerce reconciliation across ledger and transaction gateway.
SELECT 
    'check_3_payment_vs_items_freight' AS check_name,
    'Informational: Compares order gross value with customer payment gateway total' AS description,
    'INFORMATIONAL' AS severity,
    COUNT(*) AS failed_rows,
    'Flag orders in mart (has_payment_discrepancy=TRUE); audit installment interest and vouchers' AS remediation
FROM (
    WITH item_ledger AS (
        SELECT order_id, ROUND(SUM(price + freight_value), 2) AS expected_total
        FROM staging.order_items
        GROUP BY order_id
    ),
    payment_ledger AS (
        SELECT order_id, ROUND(SUM(payment_value), 2) AS paid_total
        FROM staging.payments
        GROUP BY order_id
    )
    SELECT i.order_id
    FROM item_ledger i
    JOIN payment_ledger p ON i.order_id = p.order_id
    WHERE ABS(i.expected_total - p.paid_total) > 0.05
) sub_recon

UNION ALL

-- Check 4: Orders whose customer_id has no matching customer record (CRITICAL)
-- Invariant: Foreign key referential integrity between orders and customers dimension.
SELECT 
    'check_4_orders_without_customer' AS check_name,
    'Critical: Referential integrity ensuring every order maps to a known customer' AS description,
    'CRITICAL' AS severity,
    COUNT(*) AS failed_rows,
    'Stop pipeline; repair orphan orders or customer ingestion dimension table' AS remediation
FROM staging.orders o
LEFT JOIN staging.customers c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL

UNION ALL

-- Check 5: Invalid review scores outside [1, 5] Likert scale (INFORMATIONAL / FLAG)
-- Invariant: Customer feedback ratings must conform to valid survey scale.
SELECT 
    'check_5_invalid_review_scores' AS check_name,
    'Informational: Verifies review scores adhere to the 1-5 rating scale' AS description,
    'INFORMATIONAL' AS severity,
    COUNT(*) AS failed_rows,
    'Flag records; impute NULL or quarantine malformed feedback entries' AS remediation
FROM staging.reviews
WHERE review_score IS NULL OR review_score NOT BETWEEN 1 AND 5

UNION ALL

-- Check 6: Negative or zero item price / negative freight value (CRITICAL)
-- Invariant: Economic validity of transaction line items.
SELECT 
    'check_6_negative_item_prices' AS check_name,
    'Critical: Ensures price > 0 and freight >= 0 for all purchased line items' AS description,
    'CRITICAL' AS severity,
    COUNT(*) AS failed_rows,
    'Stop pipeline; investigate billing or pricing corruption in line item feed' AS remediation
FROM staging.order_items
WHERE price <= 0 OR freight_value < 0

UNION ALL

-- Check 7: Delivered date earlier than carrier handover date (INFORMATIONAL / FLAG)
-- Invariant: Package cannot be marked delivered before postal carrier picked it up.
SELECT 
    'check_7_delivered_before_carrier' AS check_name,
    'Informational: Logistics chronological check for carrier dispatched vs delivered' AS description,
    'INFORMATIONAL' AS severity,
    COUNT(*) AS failed_rows,
    'Flag logistics tracking anomaly; investigate postal barcode scan synchronization lag' AS remediation
FROM staging.orders
WHERE carrier_ts IS NOT NULL 
  AND delivered_ts IS NOT NULL 
  AND delivered_ts < carrier_ts;
