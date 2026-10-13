-- ==============================================================================
-- ASSIGNMENT PART C: QUESTION 1
-- "Month-over-month revenue and percentage growth using LAG."
-- 
-- LOGIC & DESIGN:
-- 1. Aggregates gross order value (items + freight) by purchase calendar month.
-- 2. Excludes canceled and unavailable orders as they do not generate net realized GMV.
-- 3. Uses LAG(monthly_revenue, 1) OVER (ORDER BY order_month) to retrieve the prior month's revenue.
-- 4. Handles division by zero via NULLIF(prev_month_revenue, 0).
-- 5. Derives absolute change and relative percentage growth rate rounded to 2 decimals.
--
-- RESULTS & LIMITATIONS:
-- - In late 2016, Olist operated in soft-launch/pilot mode (e.g. 2 orders in Sept 2016, 0 in Nov 2016).
-- - Peak revenue occurred in November 2017 (Black Friday) reaching R$ 1,172,191.68 (+53.28% MoM).
-- - In 2018, revenue stabilized at approximately R$ 1.0M - 1.15M monthly.
-- - September 2018 is incomplete due to dataset end date truncation.
-- ==============================================================================

WITH monthly_revenue AS (
    SELECT 
        date_trunc('month', purchase_ts)::DATE AS order_month,
        ROUND(SUM(gross_order_value), 2) AS monthly_revenue,
        COUNT(DISTINCT order_id) AS order_count
    FROM mart.order_summary
    WHERE order_status NOT IN ('canceled', 'unavailable')
      AND purchase_ts IS NOT NULL
    GROUP BY 1
),
with_lag AS (
    SELECT 
        order_month,
        monthly_revenue,
        order_count,
        LAG(monthly_revenue, 1) OVER (ORDER BY order_month) AS prev_month_revenue
    FROM monthly_revenue
)
SELECT 
    order_month,
    monthly_revenue,
    prev_month_revenue,
    ROUND(monthly_revenue - prev_month_revenue, 2) AS mom_revenue_change,
    ROUND(
        100.0 * (monthly_revenue - prev_month_revenue) / NULLIF(prev_month_revenue, 0),
        2
    ) AS mom_growth_pct,
    order_count
FROM with_lag
ORDER BY order_month;
