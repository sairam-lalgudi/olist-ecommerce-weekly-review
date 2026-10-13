-- ==============================================================================
-- ASSIGNMENT PART C: QUESTION 5
-- "Average delivery delay compared with estimated delivery date, and its relationship with review score."
-- 
-- LOGIC & DESIGN:
-- 1. Evaluates delivered orders with non-null delivered_ts, estimated_ts, and review_score.
-- 2. Delivery delay is defined as date_diff('second', estimated_ts, delivered_ts) / 86400.0:
--    - Negative values represent deliveries ahead of schedule (early).
--    - Zero represents on-schedule delivery on the estimated date.
--    - Positive values represent late deliveries exceeding the customer commitment date.
-- 3. Segmented into 5 granular operational buckets:
--    - '>7 days early', '1-7 days early', 'On estimated date', '1-7 days late', '>7 days late'.
-- 4. Computes order volume, percentage share, average delay in days, average review score,
--    and distribution of extreme ratings (5-star vs 1-star).
-- 
-- RESULTS & LIMITATIONS:
-- - Overall on-time performance: 92.01% of delivered orders arrive early or on-time (avg review: 4.29).
-- - Non-linear penalty cliff:
--    * 1-7 days late: Average review score collapses from 4.29 to 3.18 (-25.9%), with 1-star reviews surging to 29.57%.
--    * >7 days late: Average review score plunges to 1.73 (-59.7%), with 68.66% receiving 1-star ratings!
-- - Limitations: Observational correlation does not isolate whether poor review scores stem exclusively
--   from delivery lateness or compounding seller product defects, but the statistical divergence is dramatic.
-- ==============================================================================

WITH delivered_orders AS (
    SELECT 
        order_id,
        delivery_delay_days,
        review_score,
        CASE 
            WHEN delivery_delay_days < -7 THEN '1. >7 days early'
            WHEN delivery_delay_days < 0 THEN '2. 1-7 days early'
            WHEN delivery_delay_days = 0 THEN '3. On estimated date'
            WHEN delivery_delay_days <= 7 THEN '4. 1-7 days late'
            ELSE '5. >7 days late'
        END AS delay_bucket,
        CASE 
            WHEN delivery_delay_days <= 0 THEN 'On-Time or Early'
            ELSE 'Late'
        END AS on_time_category
    FROM mart.order_summary
    WHERE order_status = 'delivered'
      AND delivered_ts IS NOT NULL
      AND estimated_ts IS NOT NULL
      AND review_score IS NOT NULL
)
SELECT 
    delay_bucket,
    on_time_category,
    COUNT(*) AS total_orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS order_share_pct,
    ROUND(AVG(delivery_delay_days), 2) AS avg_delay_days,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 5) / COUNT(*), 2) AS pct_5_star_reviews,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 1) / COUNT(*), 2) AS pct_1_star_reviews
FROM delivered_orders
GROUP BY delay_bucket, on_time_category
ORDER BY delay_bucket;
