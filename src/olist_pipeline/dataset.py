"""Canonical source-dataset contract used by profiling and validation."""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class TableContract:
    filename: str
    required_columns: Tuple[str, ...]
    natural_key: Tuple[str, ...]


TABLES: Dict[str, TableContract] = {
    "customers": TableContract(
        "olist_customers_dataset.csv",
        (
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ),
        ("customer_id",),
    ),
    "geolocation": TableContract(
        "olist_geolocation_dataset.csv",
        (
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ),
        (),
    ),
    "order_items": TableContract(
        "olist_order_items_dataset.csv",
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ),
        ("order_id", "order_item_id"),
    ),
    "order_payments": TableContract(
        "olist_order_payments_dataset.csv",
        (
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ),
        ("order_id", "payment_sequential"),
    ),
    "order_reviews": TableContract(
        "olist_order_reviews_dataset.csv",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
        (),
    ),
    "orders": TableContract(
        "olist_orders_dataset.csv",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        ("order_id",),
    ),
    "products": TableContract(
        "olist_products_dataset.csv",
        (
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        ("product_id",),
    ),
    "sellers": TableContract(
        "olist_sellers_dataset.csv",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
        ("seller_id",),
    ),
    "category_translation": TableContract(
        "product_category_name_translation.csv",
        ("product_category_name", "product_category_name_english"),
        ("product_category_name",),
    ),
}


FOREIGN_KEYS = (
    ("orders", ("customer_id",), "customers", ("customer_id",)),
    ("order_items", ("order_id",), "orders", ("order_id",)),
    ("order_items", ("product_id",), "products", ("product_id",)),
    ("order_items", ("seller_id",), "sellers", ("seller_id",)),
    ("order_payments", ("order_id",), "orders", ("order_id",)),
    ("order_reviews", ("order_id",), "orders", ("order_id",)),
)


DATE_COLUMNS = {
    "order_items": ("shipping_limit_date",),
    "order_reviews": ("review_creation_date", "review_answer_timestamp"),
    "orders": (
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
}


NUMERIC_COLUMNS = {
    "geolocation": ("geolocation_lat", "geolocation_lng"),
    "order_items": ("price", "freight_value"),
    "order_payments": ("payment_installments", "payment_value"),
    "order_reviews": ("review_score",),
    "products": (
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ),
}
