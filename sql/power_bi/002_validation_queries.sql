-- Execute in Snowflake after applying 001_operational_reporting_views.sql.
-- These aggregate queries contain no connection or credential material.

SELECT
    COUNT(DISTINCT order_id) AS total_orders,
    ROUND(SUM(payment_total_value), 2) AS total_payment_value,
    ROUND(SUM(payment_total_value) / COUNT(DISTINCT order_id), 2) AS average_order_value,
    ROUND(SUM(item_merchandise_value), 2) AS merchandise_value,
    ROUND(SUM(freight_value), 2) AS freight_value,
    COUNT(DISTINCT customer_key) AS customer_count,
    COUNT_IF(order_status = 'delivered') AS delivered_orders,
    COUNT_IF(order_status = 'delivered' AND is_late_delivery) AS late_deliveries,
    COUNT_IF(order_status = 'delivered' AND NOT is_late_delivery) AS on_time_deliveries,
    COUNT_IF(order_status = 'delivered' AND is_late_delivery IS NULL)
        AS unknown_timeliness_deliveries
FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS;

SELECT
    COUNT(DISTINCT product_key) AS product_count,
    COUNT(DISTINCT seller_key) AS seller_count
FROM OLIST_ELT.MARTS.REPORT_FCT_ORDER_ITEMS;

SELECT
    order_status,
    COUNT(*) AS total_orders,
    ROUND(SUM(payment_total_value), 2) AS total_payment_value
FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS
GROUP BY order_status
ORDER BY order_status;

SELECT
    date.year_number,
    date.month_number,
    COUNT(DISTINCT orders.order_id) AS total_orders,
    ROUND(SUM(orders.payment_total_value), 2) AS total_payment_value
FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS AS orders
INNER JOIN OLIST_ELT.MARTS.REPORT_DIM_DATE AS date
    ON orders.purchase_date_key = date.date_key
GROUP BY date.year_number, date.month_number
ORDER BY date.year_number, date.month_number;

SELECT
    (SELECT ROUND(SUM(item_price), 2)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDER_ITEMS) AS item_detail_merchandise,
    (SELECT ROUND(SUM(item_merchandise_value), 2)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS) AS order_merchandise,
    (SELECT ROUND(SUM(freight_value), 2)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDER_ITEMS) AS item_detail_freight,
    (SELECT ROUND(SUM(freight_value), 2)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS) AS order_freight,
    (SELECT ROUND(SUM(payment_value), 2)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDER_PAYMENTS) AS payment_detail,
    (SELECT ROUND(SUM(payment_total_value), 2)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS) AS order_payment;

SELECT
    (SELECT COUNT(*)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDERS AS fact
     LEFT JOIN OLIST_ELT.MARTS.REPORT_DIM_DATE AS dim
        ON fact.purchase_date_key = dim.date_key
     WHERE dim.date_key IS NULL) AS order_date_orphans,
    (SELECT COUNT(*)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDER_ITEMS AS fact
     LEFT JOIN OLIST_ELT.MARTS.REPORT_DIM_PRODUCT AS dim
        ON fact.product_key = dim.product_key
     WHERE dim.product_key IS NULL) AS item_product_orphans,
    (SELECT COUNT(*)
     FROM OLIST_ELT.MARTS.REPORT_FCT_ORDER_ITEMS AS fact
     LEFT JOIN OLIST_ELT.MARTS.REPORT_DIM_SELLER AS dim
        ON fact.seller_key = dim.seller_key
     WHERE dim.seller_key IS NULL) AS item_seller_orphans;

SELECT * FROM OLIST_ELT.AUDIT.PBI_PIPELINE_HEALTH;
SELECT * FROM OLIST_ELT.AUDIT.PBI_SOURCE_FRESHNESS ORDER BY source_name;
SELECT * FROM OLIST_ELT.AUDIT.PBI_PIPELINE_RUNS ORDER BY started_at;
