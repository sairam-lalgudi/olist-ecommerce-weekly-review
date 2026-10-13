# Data Dictionary & Schema Documentation

## 1. Raw Ingestion Layer (`raw.*`)
The raw schema mirrors the incoming CSV files without schema mutations or column deletions:

| Table | Source File | Grain | Row Count | Primary Key |
|---|---|---|---|---|
| `raw.orders` | `olist_orders_dataset.csv` | Order | 99,441 | `order_id` |
| `raw.order_items` | `olist_order_items_dataset.csv` | Order Line Item | 112,650 | `(order_id, order_item_id)` |
| `raw.payments` | `olist_order_payments_dataset.csv` | Payment Sequence | 103,886 | `(order_id, payment_sequential)` |
| `raw.reviews` | `olist_order_reviews_dataset.csv` | Customer Review | 99,224 | `review_id` |
| `raw.customers` | `olist_customers_dataset.csv` | Customer Token | 99,441 | `customer_id` |
| `raw.products` | `olist_products_dataset.csv` | Catalog Product | 32,951 | `product_id` |
| `raw.sellers` | `olist_sellers_dataset.csv` | Merchant Seller | 3,095 | `seller_id` |
| `raw.geolocation` | `olist_geolocation_dataset.csv` | Zip Prefix Point | 1,000,163 | Composite |
| `raw.category_translation` | `product_category_name_translation.csv` | Category Translation | 71 | `product_category_name` |

---

## 2. Cleaned Staging Layer (`staging.*`)
Staging tables apply type coercion, whitespace trimming, and timestamp standardization:

### `staging.orders`
- `order_id` (VARCHAR): Unique 32-character hex order identifier.
- `customer_id` (VARCHAR): Transaction-specific surrogate token. Foreign key to `staging.customers(customer_id)`.
- `order_status` (VARCHAR): Current lifecycle state (`delivered`, `shipped`, `canceled`, `invoiced`, `processing`, `unavailable`).
- `purchase_ts` (TIMESTAMP): Order placement timestamp.
- `approved_ts` (TIMESTAMP): Payment authorization timestamp.
- `carrier_ts` (TIMESTAMP): Postal handover/pickup timestamp.
- `delivered_ts` (TIMESTAMP): Customer receipt confirmation timestamp.
- `estimated_ts` (TIMESTAMP): Promised estimated delivery commitment date.

### `staging.order_items`
- `order_id` (VARCHAR): Foreign key to `staging.orders(order_id)`.
- `order_item_id` (INTEGER): Sequential line number per order (1, 2, 3...).
- `product_id` (VARCHAR): Foreign key to `staging.products(product_id)`.
- `seller_id` (VARCHAR): Merchant identifier.
- `shipping_limit_ts` (TIMESTAMP): Merchant dispatch deadline.
- `price` (DOUBLE): Item purchase price in Brazilian Real (BRL).
- `freight_value` (DOUBLE): Shipping charge allocated to this item in BRL.

### `staging.payments`
- `order_id` (VARCHAR): Foreign key to `staging.orders(order_id)`.
- `payment_sequential` (INTEGER): Payment attempt/sequence sequence.
- `payment_type` (VARCHAR): Payment instrument (`credit_card`, `boleto`, `voucher`, `debit_card`).
- `payment_installments` (INTEGER): Number of installment terms selected.
- `payment_value` (DOUBLE): Amount charged through gateway.

### `staging.reviews`
- `review_id` (VARCHAR): Unique feedback identifier.
- `order_id` (VARCHAR): Foreign key to `staging.orders(order_id)`.
- `review_score` (INTEGER): Likert satisfaction rating from 1 to 5.
- `review_comment_title` (VARCHAR): Optional feedback subject headline.
- `review_comment_message` (VARCHAR): Customer feedback text narrative.
- `review_creation_ts` (TIMESTAMP): Survey issuance timestamp.
- `review_answer_ts` (TIMESTAMP): Survey response submission timestamp.

### `staging.customers`
- `customer_id` (VARCHAR): Transaction-specific token.
- `customer_unique_id` (VARCHAR): Persistent real-world customer identity across orders.
- `customer_zip_code_prefix` (VARCHAR): Brazilian 5-digit postal prefix (CEP).
- `customer_city` (VARCHAR): City name.
- `customer_state` (VARCHAR): 2-letter Brazilian state abbreviation (e.g. SP, RJ, MG).

---

## 3. Curated Dimensional Mart (`mart.order_summary`)
The flagship analytical mart. Materializes **exactly one row per order**:

| Column Name | Data Type | Grain / Aggregation Logic | Description |
|---|---|---|---|
| `order_id` | VARCHAR | Primary Key | Unique order identifier |
| `customer_id` | VARCHAR | Dimension | Order-specific customer surrogate |
| `customer_unique_id` | VARCHAR | Dimension | Persistent customer identity |
| `customer_state` | VARCHAR | Dimension | Customer recipient state |
| `order_status` | VARCHAR | Dimension | Order lifecycle state |
| `purchase_ts` | TIMESTAMP | Fact | Order placement timestamp |
| `approved_ts` | TIMESTAMP | Fact | Payment approval timestamp |
| `carrier_ts` | TIMESTAMP | Fact | Logistics handover timestamp |
| `delivered_ts` | TIMESTAMP | Fact | Customer delivery timestamp |
| `estimated_ts` | TIMESTAMP | Fact | Estimated delivery date |
| `item_total` | DOUBLE | SUM(price) | Sum of all line item prices |
| `freight_total` | DOUBLE | SUM(freight_value) | Sum of all shipping charges |
| `gross_order_value` | DOUBLE | SUM(price + freight) | Total order gross merchandise value |
| `item_count` | INTEGER | COUNT(*) items | Number of distinct items in order |
| `payment_total` | DOUBLE | SUM(payment_value) | Total funds captured by gateway |
| `payment_count` | INTEGER | COUNT(*) payments | Number of payment transactions |
| `max_installments` | INTEGER | MAX(installments) | Highest installment count used |
| `payment_types` | VARCHAR | STRING_AGG() | Concatenated list of payment methods |
| `review_score` | DOUBLE | AVG(review_score) | Average customer satisfaction rating (1-5) |
| `review_count` | INTEGER | COUNT(*) reviews | Total reviews submitted for order |
| `delivery_delay_days` | DOUBLE | date_diff('second', estimated, delivered) / 86400 | Days difference from promised date (negative=early, positive=late) |
| `delivery_duration_days`| DOUBLE | date_diff('second', purchase, delivered) / 86400 | Total elapsed transit duration from purchase to customer door |
| `has_payment_discrepancy`| BOOLEAN | ABS(gross_order_value - payment_total) > 0.05 | Financial reconciliation audit flag |
