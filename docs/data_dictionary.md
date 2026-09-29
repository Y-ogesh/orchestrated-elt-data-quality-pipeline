# Data dictionary

The source spelling is retained in RAW, including Olist's `*_lenght` fields. STAGING will expose corrected `*_length` aliases. Blank CSV values become SQL `NULL`; identifiers and postal prefixes remain strings.

## Source contracts

### `olist_customers_dataset.csv` — one row per order-specific `customer_id`

| Column | Type | Meaning |
|---|---|---|
| `customer_id` | string | Order-specific customer key; unique and referenced by orders |
| `customer_unique_id` | string | Person-level identifier used to recognize repeat purchasers |
| `customer_zip_code_prefix` | string | Five-digit delivery postal prefix |
| `customer_city` | string | Delivery city |
| `customer_state` | string | Two-letter Brazilian state code |

### `olist_geolocation_dataset.csv` — source observation at postal prefix/coordinate/city/state grain

| Column | Type | Meaning |
|---|---|---|
| `geolocation_zip_code_prefix` | string | Postal prefix; non-unique |
| `geolocation_lat` / `geolocation_lng` | decimal | Coordinate observation |
| `geolocation_city` | string | Observed city spelling |
| `geolocation_state` | string | State code |

There is no source natural key. Exact duplicates exist. `dim_geography` will use one deterministic representative per postal prefix (median valid coordinate, normalized modal city/state), while retaining exception counts.

### `olist_orders_dataset.csv` — one row per `order_id`

| Column | Type | Meaning |
|---|---|---|
| `order_id` | string | Unique order key |
| `customer_id` | string | FK to the order-specific customer row |
| `order_status` | string | Source lifecycle status |
| `order_purchase_timestamp` | timestamp | Purchase time; historical replay driver |
| `order_approved_at` | timestamp | Payment approval time, nullable |
| `order_delivered_carrier_date` | timestamp | Carrier handoff time, nullable |
| `order_delivered_customer_date` | timestamp | Customer delivery time, nullable |
| `order_estimated_delivery_date` | timestamp | Promised delivery date |

### `olist_order_items_dataset.csv` — one row per (`order_id`, `order_item_id`)

| Column | Type | Meaning |
|---|---|---|
| `order_id` | string | FK to orders |
| `order_item_id` | integer | One-based line sequence within an order |
| `product_id` | string | FK to products |
| `seller_id` | string | FK to sellers |
| `shipping_limit_date` | timestamp | Seller shipping deadline |
| `price` | decimal(18,2) | Item merchandise value in BRL |
| `freight_value` | decimal(18,2) | Item-attributed freight value in BRL |

### `olist_order_payments_dataset.csv` — one row per (`order_id`, `payment_sequential`)

| Column | Type | Meaning |
|---|---|---|
| `order_id` | string | FK to orders |
| `payment_sequential` | integer | Payment sequence within the order |
| `payment_type` | string | Credit card, boleto, voucher, debit card, or source `not_defined` |
| `payment_installments` | integer | Installment count; two source rows contain zero |
| `payment_value` | decimal(18,2) | Tendered value in BRL; nine source rows contain zero |

### `olist_order_reviews_dataset.csv` — one row per source review record

| Column | Type | Meaning |
|---|---|---|
| `review_id` | string | Review identifier; **not unique** in this snapshot |
| `order_id` | string | FK to orders; also non-unique |
| `review_score` | integer | Score from 1 through 5 |
| `review_comment_title` | string | Optional title |
| `review_comment_message` | string | Optional review text |
| `review_creation_date` | timestamp | Review creation time |
| `review_answer_timestamp` | timestamp | Answer/submission timestamp |

The staged record key is a hash of all normalized source fields. Exact duplicate future records will be quarantined because the source provides no stable occurrence identifier.

### `olist_products_dataset.csv` — one row per `product_id`

| Column | Type | Meaning |
|---|---|---|
| `product_id` | string | Unique product key |
| `product_category_name` | string | Portuguese category, nullable |
| `product_name_lenght` | integer | Source-spelled product-name length, nullable |
| `product_description_lenght` | integer | Source-spelled description length, nullable |
| `product_photos_qty` | integer | Photo count, nullable |
| `product_weight_g` | decimal | Weight in grams, nullable |
| `product_length_cm` / `product_height_cm` / `product_width_cm` | decimal | Package dimensions, nullable |

### `olist_sellers_dataset.csv` — one row per `seller_id`

| Column | Type | Meaning |
|---|---|---|
| `seller_id` | string | Unique seller key |
| `seller_zip_code_prefix` | string | Seller postal prefix |
| `seller_city` | string | Seller city |
| `seller_state` | string | Seller state code |

### `product_category_name_translation.csv` — one row per Portuguese category

| Column | Type | Meaning |
|---|---|---|
| `product_category_name` | string | Portuguese category key |
| `product_category_name_english` | string | English label |

The official file begins with a UTF-8 BOM. Two product categories have no translation and will map to a documented `unknown/untranslated` member, not be dropped.

## Reporting model grains and keys

| Model | Grain | Business/unique key | Principal measures or attributes |
|---|---|---|---|
| `fct_orders` | One order | `order_id` | status, lifecycle timestamps, item merchandise, freight, item total, payment total, reconciliation difference, delivery days, late flag |
| `fct_order_items` | One order line | (`order_id`, `order_item_id`) | item price, freight |
| `fct_order_payments` | One payment component | (`order_id`, `payment_sequential`) | payment type, installments, payment value |
| `fct_order_reviews` | One distinct source review record | hash of normalized record | review score, optional text, review timestamps |
| `dim_customer` | One person-level customer | `customer_unique_id` | first/last order dates, customer metrics derived downstream |
| `dim_order_customer` | One order-specific customer/delivery record | `customer_id` | customer unique key, city/state/postal prefix |
| `dim_product` | One product | `product_id` | category, descriptive and physical attributes |
| `dim_seller` | One seller | `seller_id` | city/state/postal prefix |
| `dim_category` | One Portuguese category plus unknown | `product_category_name` | English label, translation-status flag |
| `dim_geography` | One postal prefix plus unknown | postal prefix | deterministic representative coordinate/city/state, observation counts |
| `dim_date` | One calendar date | date | day/week/month/quarter/year attributes |

## Metric contracts

| Metric | Definition | Guardrail |
|---|---|---|
| `item_merchandise_value` | Sum of `price` at order-item grain | Aggregate before any payment join |
| `freight_value` | Sum of item `freight_value` | Aggregate before any payment join |
| `item_total_value` | `item_merchandise_value + freight_value` | Not assumed equal to payments |
| `payment_total_value` | Sum of `payment_value` at payment grain | Aggregate before any item join |
| `payment_item_difference` | `payment_total_value - item_total_value` | Keep exceptions visible; tolerance R$0.01 |
| `delivered_gmv` | Item merchandise value for delivered orders | Label as GMV, not recognized revenue |
| `average_order_value` | Delivered GMV / distinct delivered orders | Never average item rows |
| `late_delivery` | Delivered timestamp after estimated date | Null when not delivered |
