# Dataset profiling

## Provenance and method

The snapshot was downloaded on 2026-09-29 from the [official Olist organization dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Kaggle's API metadata identifies dataset ID `55151`, title “Brazilian E-Commerce Public Dataset by Olist,” version 2, last updated 2021-10-01, size 126,186,995 bytes, and license CC BY-NC-SA 4.0.

`make profile` streams every CSV with Python's standard library, handles the translation file's UTF-8 BOM, and records SHA-256 hashes, rows, columns, nulls, distinct counts, exact duplicates, declared-key duplicates, numeric/date ranges, relationships, and selected business rules. Raw customer-level data is ignored; only aggregates are committed in `reports/data_profile.json`.

## Table summary

| Source | Rows | Columns | Natural key | Key duplicate rows | Exact duplicate rows |
|---|---:|---:|---|---:|---:|
| Customers | 99,441 | 5 | `customer_id` | 0 | 0 |
| Geolocation | 1,000,163 | 5 | None supplied | n/a | 261,831 |
| Order items | 112,650 | 7 | (`order_id`, `order_item_id`) | 0 | 0 |
| Order payments | 103,886 | 5 | (`order_id`, `payment_sequential`) | 0 | 0 |
| Order reviews | 99,224 | 7 | None safely inferable | n/a | 0 |
| Orders | 99,441 | 8 | `order_id` | 0 | 0 |
| Products | 32,951 | 9 | `product_id` | 0 | 0 |
| Sellers | 3,095 | 4 | `seller_id` | 0 | 0 |
| Category translation | 71 | 2 | `product_category_name` | 0 | 0 |

The parsed total is 1,550,922 records. Physical line counts are not used as record counts because quoted review text can contain embedded newlines.

## Nulls

Only nonzero null counts are shown. Empty CSV fields are treated as nulls.

| Table.column | Nulls | Interpretation |
|---|---:|---|
| `orders.order_approved_at` | 160 | Mostly canceled orders; also 14 delivered orders |
| `orders.order_delivered_carrier_date` | 1,783 | Largely expected for non-delivered states; two delivered orders are missing it |
| `orders.order_delivered_customer_date` | 2,965 | Largely expected for incomplete/canceled states; eight delivered orders are missing it |
| `order_reviews.review_comment_title` | 87,656 | Optional text |
| `order_reviews.review_comment_message` | 58,247 | Optional text |
| `products.product_category_name` | 610 | Missing descriptive classification |
| Four product descriptive fields | 610 each | Name length, description length, photo count follow category-null group |
| Five product physical fields | 2 each | Weight and package dimensions incomplete |

All other source columns have zero blank values.

## Dates and numeric boundaries

| Field | Minimum | Maximum |
|---|---:|---:|
| Order purchase timestamp | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 |
| Order delivered timestamp | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 |
| Estimated delivery date | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 |
| Item shipping limit | 2016-09-19 00:15:34 | 2020-04-09 22:35:08 |
| Review creation | 2016-10-02 00:00:00 | 2018-08-31 00:00:00 |
| Item price (BRL) | 0.85 | 6,735.00 |
| Item freight (BRL) | 0.00 | 409.68 |
| Payment value (BRL) | 0.00 | 13,664.08 |
| Review score | 1 | 5 |

## Relationship validation

All measured orphan row counts are zero:

- Orders → customers on `customer_id`.
- Order items → orders on `order_id`.
- Order items → products on `product_id`.
- Order items → sellers on `seller_id`.
- Payments → orders on `order_id`.
- Reviews → orders on `order_id`.

Postal prefix is intentionally not asserted as a strict FK: geolocation is observational, has duplicates and spelling variants, and should be reduced to a conformed geography dimension.

## Observed data-quality findings

These are present in the downloaded source and are not injected test data:

| Finding | Measured result | Planned handling |
|---|---:|---|
| Exact duplicate geolocation rows | 261,831 | Deduplicate and aggregate deterministically; preserve source count |
| Coordinates outside broad Brazil box (lat −34..6, lon −74..−34) | 42 | Flag/quarantine from representative-coordinate calculation; do not delete RAW |
| Repeated `review_id` occurrences beyond first | 814 | Do not use `review_id` alone as a key |
| Repeated review `order_id` occurrences beyond first | 551 | Support multiple reviews per order |
| Shipping-limit rows after 2018-12-31 | 4 | Flag; maximum is in 2020, well beyond purchase coverage |
| Product categories without English translation | 2 | Preserve Portuguese value and map English label to unknown/untranslated |
| Payment rows with zero installments | 2 | Quality warning; retain RAW |
| Payment rows with zero value | 9 | Quality warning; retain RAW |
| Products with zero weight | 4 | Quality warning; distinguish from null |
| Delivered after estimate | 7,827 | Valid business outcome and KPI, not rejected |
| Delivered before purchase | 0 | Blocking chronology test remains appropriate |
| Orders with items but no payments | 1 | Reconciliation exception |
| Orders with payments but no items | 775 | Often aligns with unavailable/canceled states; classify by status downstream |
| Shared orders differing by > R$0.01 | 303 | Publish difference and exception flag; never force equality |
| Maximum absolute item/payment difference | R$182.81 | Investigate downstream by order without exposing IDs in docs |

Order statuses are: 96,478 delivered; 1,107 shipped; 625 canceled; 609 unavailable; 314 invoiced; 301 processing; 5 created; and 2 approved.

## Synthetic scenarios reserved for later testing

The following are **not claims about this source snapshot**. They will be injected in isolated test fixtures to verify resilience: a truncated upload, checksum conflict, duplicate delivery event, late-arriving order item, malformed numeric value, missing required column, orphan product/seller key, Snowflake task failure, dbt test failure, retry after partial load, and stale reporting publication. Synthetic records must never enter committed profiling evidence or production-like marts.

## Reproducibility

Run `make download`, `make profile`, and `make validate`. The committed profile contains full file hashes. A different hash means a different source artifact and requires a new source version plus a reviewed profile rather than overwriting this evidence.
