"""Pytest fixtures: provides isolated synthetic CSV datasets and in-memory DuckDB instances."""
import pytest
import duckdb
from pathlib import Path

@pytest.fixture
def synthetic_data_dir(tmp_path):
    """Creates a small, fully controlled synthetic Olist dataset for deterministic unit testing."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    # 1. Orders (4 orders: 1 normal delivered, 1 early, 1 late, 1 canceled)
    orders_csv = raw_dir / "olist_orders_dataset.csv"
    orders_csv.write_text(
        "order_id,customer_id,order_status,order_purchase_timestamp,order_approved_at,order_delivered_carrier_date,order_delivered_customer_date,order_estimated_delivery_date\n"
        "ord_001,cust_001,delivered,2017-01-10 10:00:00,2017-01-10 10:30:00,2017-01-12 14:00:00,2017-01-18 16:00:00,2017-01-25 00:00:00\n"
        "ord_002,cust_002,delivered,2017-01-15 12:00:00,2017-01-15 13:00:00,2017-01-17 09:00:00,2017-01-22 18:00:00,2017-01-20 00:00:00\n"
        "ord_003,cust_001_repeat,delivered,2017-02-05 14:00:00,2017-02-05 15:00:00,2017-02-07 10:00:00,2017-02-12 11:00:00,2017-02-15 00:00:00\n"
        "ord_004,cust_003,canceled,2017-02-10 09:00:00,,,,2017-02-28 00:00:00\n"
    )

    # 2. Order Items (ord_001 has 2 items to test multi-item aggregation)
    items_csv = raw_dir / "olist_order_items_dataset.csv"
    items_csv.write_text(
        "order_id,order_item_id,product_id,seller_id,shipping_limit_date,price,freight_value\n"
        "ord_001,1,prod_tech,sell_01,2017-01-15 10:00:00,100.00,15.00\n"
        "ord_001,2,prod_tech,sell_01,2017-01-15 10:00:00,50.00,10.00\n"
        "ord_002,1,prod_home,sell_02,2017-01-20 12:00:00,200.00,25.00\n"
        "ord_003,1,prod_tech,sell_01,2017-02-10 14:00:00,120.00,18.00\n"
        "ord_004,1,prod_home,sell_02,2017-02-15 09:00:00,80.00,12.00\n"
    )

    # 3. Payments (ord_001 has 2 split payments: voucher + credit card)
    payments_csv = raw_dir / "olist_order_payments_dataset.csv"
    payments_csv.write_text(
        "order_id,payment_sequential,payment_type,payment_installments,payment_value\n"
        "ord_001,1,voucher,1,25.00\n"
        "ord_001,2,credit_card,3,150.00\n"
        "ord_002,1,credit_card,1,225.00\n"
        "ord_003,1,boleto,1,138.00\n"
        "ord_004,1,credit_card,1,92.00\n"
    )

    # 4. Reviews (ord_001 has 1 review, ord_002 has 1 review)
    reviews_csv = raw_dir / "olist_order_reviews_dataset.csv"
    reviews_csv.write_text(
        "review_id,order_id,review_score,review_comment_title,review_comment_message,review_creation_date,review_answer_timestamp\n"
        "rev_001,ord_001,5,Great,Delivered early and works perfectly,2017-01-19 00:00:00,2017-01-20 10:00:00\n"
        "rev_002,ord_002,1,Late,Package arrived late,2017-01-23 00:00:00,2017-01-24 12:00:00\n"
        "rev_003,ord_003,4,,Good purchase,2017-02-13 00:00:00,2017-02-14 09:00:00\n"
    )

    # 5. Customers (cust_001 and cust_001_repeat share user_uuid_alpha -> repeat customer!)
    customers_csv = raw_dir / "olist_customers_dataset.csv"
    customers_csv.write_text(
        "customer_id,customer_unique_id,customer_zip_code_prefix,customer_city,customer_state\n"
        "cust_001,user_uuid_alpha,01310,sao paulo,SP\n"
        "cust_002,user_uuid_beta,20040,rio de janeiro,RJ\n"
        "cust_001_repeat,user_uuid_alpha,01310,sao paulo,SP\n"
        "cust_003,user_uuid_gamma,30130,belo horizonte,MG\n"
    )

    # 6. Products
    products_csv = raw_dir / "olist_products_dataset.csv"
    products_csv.write_text(
        "product_id,product_category_name,product_name_lenght,product_description_lenght,product_photos_qty,product_weight_g,product_length_cm,product_height_cm,product_width_cm\n"
        "prod_tech,informatica_acessorios,40,250,2,500,20,10,15\n"
        "prod_home,cama_mesa_banho,35,300,1,1200,30,15,20\n"
    )

    # 7. Category translation
    trans_csv = raw_dir / "product_category_name_translation.csv"
    trans_csv.write_text(
        "product_category_name,product_category_name_english\n"
        "informatica_acessorios,computers_accessories\n"
        "cama_mesa_banho,bed_bath_table\n"
    )

    return raw_dir

@pytest.fixture
def mem_db():
    """Provides an isolated in-memory DuckDB instance."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()
