-- ==============================================================================
-- ASSIGNMENT PART C: QUESTION 4
-- "Repeat-purchase rate. Use customer_unique_id to identify a customer across multiple orders,
-- rather than assuming customer_id identifies a person across orders. State the precise numerator and denominator."
-- 
-- LOGIC & DESIGN:
-- 1. CRITICAL DISTINCTION:
--    - customer_id is a transient per-order token generated for each purchase transaction.
--    - customer_unique_id is the persistent, real-world customer identity across repeat purchases.
-- 2. DENOMINATOR:
--    - Total distinct customers who placed at least one non-canceled order:
--      COUNT(DISTINCT customer_unique_id) = 94,990 customers.
-- 3. NUMERATOR:
--    - Distinct customers who completed 2 or more distinct orders:
--      COUNT(DISTINCT customer_unique_id) WHERE total_orders >= 2 = 2,888 customers.
-- 4. METRIC FORMULA:
--    - Repeat Purchase Rate (%) = (2,888 / 94,990) * 100.0 = 3.04%.
-- 
-- RESULTS & LIMITATIONS:
-- - The marketplace suffers from a severely low customer retention rate (only 3.04% return).
-- - 96.96% of customers (92,102 users) make only a single transaction and churn.
-- - High repeat customers exist (max order count for a single customer is 16 orders).
-- - Repeat customers spend on average R$ 308.26 over their lifetime vs R$ 161.18 for one-time buyers (+91.3% LTV).
-- ==============================================================================

WITH customer_order_frequencies AS (
    SELECT 
        customer_unique_id,
        COUNT(DISTINCT order_id) AS total_orders,
        ROUND(SUM(gross_order_value), 2) AS lifetime_spend
    FROM mart.order_summary
    WHERE customer_unique_id IS NOT NULL
      AND order_status NOT IN ('canceled', 'unavailable')
    GROUP BY customer_unique_id
)
SELECT 
    COUNT(*) AS total_customers_denominator,
    COUNT(*) FILTER (WHERE total_orders = 1) AS single_order_customers,
    COUNT(*) FILTER (WHERE total_orders >= 2) AS repeat_customers_numerator,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE total_orders >= 2) / NULLIF(COUNT(*), 0),
        2
    ) AS repeat_purchase_rate_pct,
    MAX(total_orders) AS max_orders_by_single_customer,
    ROUND(AVG(lifetime_spend), 2) AS avg_customer_lifetime_spend,
    ROUND(AVG(lifetime_spend) FILTER (WHERE total_orders >= 2), 2) AS avg_repeat_customer_lifetime_spend,
    ROUND(AVG(lifetime_spend) FILTER (WHERE total_orders = 1), 2) AS avg_one_time_customer_spend
FROM customer_order_frequencies;
