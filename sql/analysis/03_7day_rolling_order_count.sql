-- ==============================================================================
-- ASSIGNMENT PART C: QUESTION 3
-- "Seven-day rolling average of daily order count, including calendar dates with zero orders where practical."
-- 
-- LOGIC & DESIGN:
-- 1. Establishes min and max purchase dates to generate a continuous daily calendar spine via UNNEST(range()).
-- 2. Aggregates distinct orders by purchase calendar date from mart.order_summary.
-- 3. Left-joins the daily calendar spine with actual order counts, imputing 0 for days without orders.
-- 4. Computes a 7-day rolling window: AVG(daily_order_count) OVER (ORDER BY calendar_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW).
-- 
-- RESULTS & LIMITATIONS:
-- - Covers a complete span of 774 calendar dates (September 2016 to October 2018).
-- - Successfully accounts for 140 days with zero orders (predominantly in late 2016 during pre-launch).
-- - Highlights demand spikes: November 24, 2017 (Black Friday) achieved the all-time peak of 1,176 orders,
--   driving the 7-day rolling average up to 476.14 orders/day.
-- ==============================================================================

WITH date_bounds AS (
    SELECT 
        MIN(purchase_ts::DATE) AS min_date,
        MAX(purchase_ts::DATE) AS max_date
    FROM mart.order_summary
    WHERE purchase_ts IS NOT NULL
),
calendar AS (
    SELECT UNNEST(range(min_date, max_date + INTERVAL 1 DAY, INTERVAL 1 DAY))::DATE AS calendar_date
    FROM date_bounds
),
daily_orders AS (
    SELECT 
        purchase_ts::DATE AS order_date,
        COUNT(DISTINCT order_id) AS order_count
    FROM mart.order_summary
    WHERE purchase_ts IS NOT NULL
    GROUP BY 1
),
calendar_filled AS (
    SELECT 
        c.calendar_date,
        COALESCE(d.order_count, 0) AS daily_order_count
    FROM calendar c
    LEFT JOIN daily_orders d ON c.calendar_date = d.order_date
)
SELECT 
    calendar_date,
    daily_order_count,
    ROUND(
        AVG(daily_order_count) OVER (
            ORDER BY calendar_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS rolling_7day_avg_orders
FROM calendar_filled
ORDER BY calendar_date;
