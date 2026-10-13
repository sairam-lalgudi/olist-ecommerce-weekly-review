# Weekly Business Review (WBR) Metric Definitions

This document details the mathematical formulas, data grains, and strategic rationale for every metric tracked in the executive reporting suite.

---

## 1. North Star Metric: Net Marketplace GMV
- **Mathematical Formula:**  
  $$\text{Net GMV} = \sum_{\text{order } \in \text{Valid Orders}} (\text{item\_total} + \text{freight\_total})$$
- **Filtering Predicate:** `order_status NOT IN ('canceled', 'unavailable')`
- **Data Grain:** Aggregated across completed/valid orders over the reporting period.
- **Audited Dataset Value:** **R$ 15,735,527.03**
- **Business Justification:** Net Gross Merchandise Value (GMV) reflects total commercial transaction throughput across the marketplace. It measures platform commercial scale, merchant sales volume, and the monetization base from which marketplace take-rates and commission fees are extracted.

---

## 2. Supporting Metric 1: Customer Repeat Purchase Rate
- **Mathematical Formula:**  
  $$\text{Repeat Purchase Rate (\%)} = \left( \frac{\text{Unique Customers with } \ge 2 \text{ Orders}}{\text{Total Unique Customers}} \right) \times 100$$
- **Identity Key:** `customer_unique_id` (resolves real-world individuals across orders; distinct from per-transaction `customer_id`).
- **Data Grain:** Unique customer profile.
- **Numerator:** 2,888 customers who placed 2 or more orders.
- **Denominator:** 94,990 unique customers who completed at least 1 valid order.
- **Audited Dataset Value:** **3.04%**
- **Business Justification:** Measures long-term customer loyalty and organic retention. A 3.04% repeat purchase rate indicates that 96.96% of customers transact only once and churn, exposing extreme reliance on continuous and costly performance marketing acquisition.
- **Economic Value:** Repeat customers generate an average lifetime spend of **R$ 308.26** compared to **R$ 161.18** for one-time buyers (+91.3% higher Customer Lifetime Value).

---

## 3. Supporting Metric 2: On-Time Delivery Rate
- **Mathematical Formula:**  
  $$\text{On-Time Delivery Rate (\%)} = \left( \frac{\text{Delivered Orders with } \text{delivery\_delay\_days} \le 0}{\text{Total Delivered Orders with Estimated Dates}} \right) \times 100$$
- **Data Grain:** Delivered order with non-null `delivered_ts` and `estimated_ts`.
- **Numerator:** 88,650 orders delivered on or before the promised estimated date.
- **Denominator:** 96,470 delivered orders with valid delivery and estimated timestamps.
- **Audited Dataset Value:** **91.89%**
- **Business Justification:** Primary logistics operational SLA. Measures fulfillment reliability and carrier adherence to customer commitments made at checkout.

---

## 4. Guardrail Metric: Severe Delay Defect Rate (>7 Days Late)
- **Mathematical Formula:**  
  $$\text{Severe Delay Defect Rate (\%)} = \left( \frac{\text{Delivered Orders with } \text{delivery\_delay\_days} > 7}{\text{Total Delivered Orders}} \right) \times 100$$
- **Data Grain:** Delivered order.
- **Numerator:** 3,341 orders delivered more than 7 calendar days past the promised estimated date.
- **Denominator:** 96,470 total delivered orders.
- **Audited Dataset Value:** **3.46%**
- **Business Justification:** Operational failure threshold. While minor delays (1–7 days) reduce review scores to 3.18, severe delays (>7 days) precipitate catastrophic customer sentiment collapse to **1.73 / 5.00**, with **68.66% awarding 1-star reviews**.

---

## 5. Supporting Metric 3: Average Customer Satisfaction (CSAT)
- **Mathematical Formula:**  
  $$\text{Average CSAT} = \frac{1}{N} \sum_{i=1}^{N} \text{review\_score}_i$$
- **Rating Bounds:** 1 to 5 integer Likert scale.
- **Data Grain:** Reviewed order.
- **Numerator:** Sum of all valid review scores across 98,673 reviewed orders.
- **Denominator:** 98,673 total valid review submissions.
- **Audited Dataset Value:** **4.09 / 5.00**
  - **5-Star Share:** 57.72% (56,952 reviews)
  - **4-Star Share:** 19.41% (19,154 reviews)
  - **3-Star Share:** 8.35% (8,236 reviews)
  - **2-Star Share:** 3.05% (3,006 reviews)
  - **1-Star Share:** 11.47% (11,325 reviews)
- **Business Justification:** Real-time customer sentiment benchmark reflecting post-delivery customer experience, seller product fidelity, and marketplace trust.
