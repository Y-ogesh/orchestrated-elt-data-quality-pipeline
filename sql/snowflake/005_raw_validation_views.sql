CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.RAW_TABLE_COUNTS AS
SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM {{DATABASE}}.{{RAW_SCHEMA}}.CUSTOMERS
UNION ALL SELECT 'geolocation', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.GEOLOCATION
UNION ALL SELECT 'order_items', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS
UNION ALL SELECT 'order_payments', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_PAYMENTS
UNION ALL SELECT 'order_reviews', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_REVIEWS
UNION ALL SELECT 'orders', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS
UNION ALL SELECT 'products', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.PRODUCTS
UNION ALL SELECT 'sellers', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.SELLERS
UNION ALL SELECT 'category_translation', COUNT(*) FROM {{DATABASE}}.{{RAW_SCHEMA}}.CATEGORY_TRANSLATION;

CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.RAW_KEY_VIOLATIONS AS
SELECT 'customers' AS table_name, COUNT(*) AS violation_count FROM (
    SELECT customer_id FROM {{DATABASE}}.{{RAW_SCHEMA}}.CUSTOMERS GROUP BY customer_id HAVING COUNT(*) > 1
)
UNION ALL SELECT 'orders', COUNT(*) FROM (
    SELECT order_id FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS GROUP BY order_id HAVING COUNT(*) > 1
)
UNION ALL SELECT 'order_items', COUNT(*) FROM (
    SELECT order_id, order_item_id FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS
    GROUP BY order_id, order_item_id HAVING COUNT(*) > 1
)
UNION ALL SELECT 'order_payments', COUNT(*) FROM (
    SELECT order_id, payment_sequential FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_PAYMENTS
    GROUP BY order_id, payment_sequential HAVING COUNT(*) > 1
)
UNION ALL SELECT 'products', COUNT(*) FROM (
    SELECT product_id FROM {{DATABASE}}.{{RAW_SCHEMA}}.PRODUCTS GROUP BY product_id HAVING COUNT(*) > 1
)
UNION ALL SELECT 'sellers', COUNT(*) FROM (
    SELECT seller_id FROM {{DATABASE}}.{{RAW_SCHEMA}}.SELLERS GROUP BY seller_id HAVING COUNT(*) > 1
)
UNION ALL SELECT 'category_translation', COUNT(*) FROM (
    SELECT product_category_name FROM {{DATABASE}}.{{RAW_SCHEMA}}.CATEGORY_TRANSLATION
    GROUP BY product_category_name HAVING COUNT(*) > 1
);

CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.RAW_RELATIONSHIP_VIOLATIONS AS
SELECT 'orders.customer_id->customers.customer_id' AS relationship, COUNT(*) AS orphan_rows
FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS child
LEFT JOIN {{DATABASE}}.{{RAW_SCHEMA}}.CUSTOMERS parent ON child.customer_id = parent.customer_id
WHERE parent.customer_id IS NULL
UNION ALL
SELECT 'order_items.order_id->orders.order_id', COUNT(*)
FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS child
LEFT JOIN {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS parent ON child.order_id = parent.order_id
WHERE parent.order_id IS NULL
UNION ALL
SELECT 'order_items.product_id->products.product_id', COUNT(*)
FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS child
LEFT JOIN {{DATABASE}}.{{RAW_SCHEMA}}.PRODUCTS parent ON child.product_id = parent.product_id
WHERE parent.product_id IS NULL
UNION ALL
SELECT 'order_items.seller_id->sellers.seller_id', COUNT(*)
FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS child
LEFT JOIN {{DATABASE}}.{{RAW_SCHEMA}}.SELLERS parent ON child.seller_id = parent.seller_id
WHERE parent.seller_id IS NULL
UNION ALL
SELECT 'order_payments.order_id->orders.order_id', COUNT(*)
FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_PAYMENTS child
LEFT JOIN {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS parent ON child.order_id = parent.order_id
WHERE parent.order_id IS NULL
UNION ALL
SELECT 'order_reviews.order_id->orders.order_id', COUNT(*)
FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_REVIEWS child
LEFT JOIN {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS parent ON child.order_id = parent.order_id
WHERE parent.order_id IS NULL;
