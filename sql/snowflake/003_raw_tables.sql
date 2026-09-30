CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.CUSTOMERS (
    customer_id VARCHAR,
    customer_unique_id VARCHAR,
    customer_zip_code_prefix VARCHAR,
    customer_city VARCHAR,
    customer_state VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);
CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.GEOLOCATION (
    geolocation_zip_code_prefix VARCHAR,
    geolocation_lat VARCHAR,
    geolocation_lng VARCHAR,
    geolocation_city VARCHAR,
    geolocation_state VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS (
    order_id VARCHAR,
    order_item_id VARCHAR,
    product_id VARCHAR,
    seller_id VARCHAR,
    shipping_limit_date VARCHAR,
    price VARCHAR,
    freight_value VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_PAYMENTS (
    order_id VARCHAR,
    payment_sequential VARCHAR,
    payment_type VARCHAR,
    payment_installments VARCHAR,
    payment_value VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_REVIEWS (
    review_id VARCHAR,
    order_id VARCHAR,
    review_score VARCHAR,
    review_comment_title VARCHAR,
    review_comment_message VARCHAR,
    review_creation_date VARCHAR,
    review_answer_timestamp VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS (
    order_id VARCHAR,
    customer_id VARCHAR,
    order_status VARCHAR,
    order_purchase_timestamp VARCHAR,
    order_approved_at VARCHAR,
    order_delivered_carrier_date VARCHAR,
    order_delivered_customer_date VARCHAR,
    order_estimated_delivery_date VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.PRODUCTS (
    product_id VARCHAR,
    product_category_name VARCHAR,
    product_name_lenght VARCHAR,
    product_description_lenght VARCHAR,
    product_photos_qty VARCHAR,
    product_weight_g VARCHAR,
    product_length_cm VARCHAR,
    product_height_cm VARCHAR,
    product_width_cm VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.SELLERS (
    seller_id VARCHAR,
    seller_zip_code_prefix VARCHAR,
    seller_city VARCHAR,
    seller_state VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{RAW_SCHEMA}}.CATEGORY_TRANSLATION (
    product_category_name VARCHAR,
    product_category_name_english VARCHAR,
    _batch_id VARCHAR NOT NULL,
    _source_file VARCHAR NOT NULL,
    _file_sha256 VARCHAR(64) NOT NULL,
    _source_version VARCHAR NOT NULL,
    _logical_ingestion_date DATE NOT NULL,
    _source_row_number NUMBER NOT NULL,
    _load_run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);
