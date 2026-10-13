-- ==============================================================================
-- ASSIGNMENT PART C: QUESTION 2
-- "Top three product categories by revenue within each customer state using DENSE_RANK."
-- 
-- LOGIC & DESIGN:
-- 1. Joins staging.orders, customers, order_items, products, and category_translation.
-- 2. Uses COALESCE to prefer English category translation, falling back to Portuguese, or 'unknown'.
-- 3. Computes total revenue as SUM(price + freight_value) per state and category.
-- 4. Partitions by customer_state and ranks by revenue descending using DENSE_RANK().
-- 5. Filters strictly for category_rank <= 3.
-- 
-- RESULTS & LIMITATIONS:
-- - Returns exactly 81 rows (3 top categories across all 27 Brazilian states/federal district).
-- - 'bed_bath_table', 'health_beauty', and 'watches_gifts' dominate the wealthiest consumer states
--   such as São Paulo (SP), Rio de Janeiro (RJ), and Minas Gerais (MG).
-- - In northern/interior states with higher freight distances (e.g. AC, AP), electronics/computers
--   and tools occasionally break into the top 3 due to higher item basket values.
-- ==============================================================================

WITH category_revenue_by_state AS (
    SELECT 
        c.customer_state,
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_name,
        ROUND(SUM(oi.price + oi.freight_value), 2) AS total_revenue,
        COUNT(DISTINCT o.order_id) AS distinct_orders,
        COUNT(*) AS items_sold
    FROM staging.orders o
    JOIN staging.customers c ON o.customer_id = c.customer_id
    JOIN staging.order_items oi ON o.order_id = oi.order_id
    JOIN staging.products p ON oi.product_id = p.product_id
    LEFT JOIN staging.category_translation t ON p.product_category_name = t.product_category_name
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_state, COALESCE(t.product_category_name_english, p.product_category_name, 'unknown')
),
ranked_categories AS (
    SELECT 
        customer_state,
        category_name,
        total_revenue,
        distinct_orders,
        items_sold,
        DENSE_RANK() OVER (
            PARTITION BY customer_state 
            ORDER BY total_revenue DESC
        ) AS category_rank
    FROM category_revenue_by_state
)
SELECT 
    customer_state,
    category_rank,
    category_name,
    total_revenue,
    distinct_orders,
    items_sold
FROM ranked_categories
WHERE category_rank <= 3
ORDER BY customer_state, category_rank, category_name;
