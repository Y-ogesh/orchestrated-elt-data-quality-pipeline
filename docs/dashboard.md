# Power BI reporting dashboard

## Status and purpose

**Milestone 9 status: Partially implemented.** The Snowflake reporting backend, metric contract, validation SQL, and real-Snowflake reconciliation are complete. A source-controlled PBIP/TMDL project now contains the 14-table Import model, 12 relationships, two Date calculated columns, 41 measures, formats, hidden technical fields, and two blank named page shells. Its JSON validates against Microsoft's published schemas and its semantic model parses with Microsoft's Analysis Services TMDL serializer. Power BI Desktop refresh, visual authoring, UI interaction validation, and screenshots are not claimed.

The intended report serves two audiences:

- marketplace leaders: order volume, tendered payment value, customer reach, delivery performance, and product/category performance;
- data and operations teams: freshness, quality outcomes, accepted/rejected accounting, pipeline runs, retries, and the current published reporting version.

Power BI consumes the eleven already validated `MARTS.REPORT_*` views. It does not bypass the atomic publication pointer or query retained `REPORT_STORE_*` versions. Three narrow views in `AUDIT` expose current operational state without duplicating pipeline logic.

## Reproducible assets

| Asset | Purpose |
|---|---|
| `sql/power_bi/001_operational_reporting_views.sql` | Defines the three Power BI operational views |
| `sql/power_bi/002_validation_queries.sql` | Independent KPI, monthly, quality, freshness, and run validation queries |
| `power_bi/semantic_model.yaml` | Tables, grains, relationships, cardinality, visibility, and formatting |
| `power_bi/measures.dax` | Exact explicit measures and calculated date columns |
| `power_bi/report_spec.yaml` | Two-page visual, slicer, interaction, and drill-through specification |
| `power_bi/OlistELTReporting/` | Microsoft-schema- and TMDL-parser-validated PBIP source project |
| `scripts/build_power_bi_project.py` | Deterministic PBIP/TMDL generator |
| `reports/power_bi_backend_validation.json` | Sanitized measured Snowflake results from 2026-10-19 |

The generated project follows Microsoft's documented PBIP layout, uses the supported TMDL semantic-model definition, and links the enhanced PBIR report to that model by relative path. Structural/parser validation is evidence that the source is well formed; it is not evidence that Desktop refreshed it or that visuals work. Desktop-created `.pbi/localSettings.json` and `.pbi/cache.abf` remain excluded as Microsoft recommends.

## Data sources and grains

| Power BI table | Snowflake source | Grain | Use |
|---|---|---|---|
| Report Orders | `MARTS.REPORT_FCT_ORDERS` | one order | order, payment, merchandise, freight, status and delivery KPIs |
| Report Order Items | `MARTS.REPORT_FCT_ORDER_ITEMS` | one order line | product, category and seller analysis |
| Report Order Payments | `MARTS.REPORT_FCT_ORDER_PAYMENTS` | one payment component | payment-method detail only |
| Report Order Reviews | `MARTS.REPORT_FCT_ORDER_REVIEWS` | one normalized source review | review analysis |
| Date | `MARTS.REPORT_DIM_DATE` | one date | the marked calendar table |
| Customers | `MARTS.REPORT_DIM_CUSTOMER` | one person-level customer | customer attributes |
| Order Customers | `MARTS.REPORT_DIM_ORDER_CUSTOMER` | one order-specific customer | delivery location |
| Products / Categories / Sellers / Geography | matching `MARTS.REPORT_DIM_*` views | one conformed member | item and location slicing |
| Pipeline Runs | `AUDIT.PBI_PIPELINE_RUNS` | one DAG run | success, failure and retry trends |
| Pipeline Health | `AUDIT.PBI_PIPELINE_HEALTH` | one current snapshot | current validated publication and quality KPIs |
| Source Freshness | `AUDIT.PBI_SOURCE_FRESHNESS` | one RAW source | current load-timestamp freshness |

Use Import mode for this fixed public snapshot and small model. Operational tables are disconnected deliberately: business slicers must not alter the current health snapshot. Active relationships filter from the one-side dimension toward the many-side fact. In particular, `Order Customers[ORDER_CUSTOMER_KEY]` is the one-side and `Report Orders[ORDER_CUSTOMER_KEY]` is the many-side, while TMDL records the relationship from fact to dimension with single-direction filtering. The complete contract, including inactive shipping/review date relationships, is in `power_bi/semantic_model.yaml`.

The category-to-product path is a small justified snowflake inside the otherwise star-oriented model. Do not enable bidirectional filtering to make category selections affect order-level payment. An order can contain several item categories, so allocating the full payment to every selected category would overstate value.

## Metric definitions and expected values

All currency is Brazilian real (BRL). “Payment value” means tendered payment recorded by Olist; it is **not accounting revenue** because the source has no commission, refund, recognition, or seller-payout ledger.

| Metric | Definition and source | Grain/filter | Validated value |
|---|---|---|---:|
| Total Orders | distinct `ORDER_ID` from Report Orders | order; all statuses | 99,441 |
| Total Payment Value | sum `PAYMENT_TOTAL_VALUE` from Report Orders | payment components pre-aggregated once per order | R$16,008,872.12 |
| Average Order Value | Total Payment Value / Total Orders | average tendered payment per order; all statuses | R$160.99 |
| Merchandise Value | sum `ITEM_MERCHANDISE_VALUE` from Report Orders | item price pre-aggregated once per order | R$13,591,643.70 |
| Freight Value | sum `FREIGHT_VALUE` from Report Orders | freight pre-aggregated once per order | R$2,251,909.54 |
| Customer Count | distinct person-level `CUSTOMER_KEY` in Report Orders | customers with an order | 96,096 |
| Product Count | distinct `PRODUCT_KEY` in Report Order Items | products appearing on an item | 32,951 |
| Seller Count | distinct `SELLER_KEY` in Report Order Items | sellers appearing on an item | 3,095 |
| Delivered Orders | orders with status `delivered` | order | 96,478 |
| Late Deliveries | delivered orders with `IS_LATE_DELIVERY = TRUE` | order | 7,826 |
| On-time Delivered Orders | delivered orders with flag explicitly false | order | 88,644 |
| Unknown Timeliness | delivered orders with a null late flag | order | 8 |
| Delivery Success Rate | Delivered Orders / Total Orders | all statuses | 97.0203% |
| On-time Delivery Rate | On-time / Delivered Orders | null timeliness is not on-time | 91.8800% |
| Late Delivery Rate | Late / Delivered Orders | null timeliness remains visible | 8.1117% |
| Accepted Rows | successful batch loaded rows from audit reconciliation | production RAW only | 1,550,922 |
| Rejected Rows | distinct traceable production load-error source lines | production only; synthetic probes excluded | 0 |
| Quality outcomes | latest successful quality task | validated execution | 156 pass / 1 warning / 0 failures |
| Latest validated run | reporting pointer joined to publication history | current published version | `m8_publication_retry_20261016` |
| Current freshness | age from RAW `_loaded_at`, not business timestamps | warn after 168h; error after 720h | warn; 9 sources at 199h on validation |

The profiling report’s 7,827 “arrived after estimated date” count is a broader source-timestamp observation. The dashboard’s 7,826 is intentionally restricted to orders whose source status is `delivered`, matching the published reporting metric.

`Delivered GMV` remains the existing merchandise-only metric for delivered orders. It is distinct from `Average Order Value`, which this report defines as tendered payment per order. Use the exact formulas in `power_bi/measures.dax`; do not create implicit sums.

## Fanout rules

- Order, payment-total, merchandise-total, freight-total and delivery measures use Report Orders only.
- Payment-method analysis may use Report Order Payments, but never join item rows to payment rows for aggregation.
- Seller/product/category visuals use `Item Orders`, `Item Merchandise Value`, and item-selection delivery measures.
- The item-selection delivery measures pass distinct order keys with `TREATAS`; they do not multiply an order by its item count.
- A category slicer filters item/category visuals. It does not filter Total Payment Value or Average Order Value because no defensible category-level payment allocation exists.

Real Snowflake validation proved identical detail/order totals for merchandise, freight, and payments and zero tested relationship orphans. The committed JSON contains those three comparisons.

## Report pages

### Executive Overview

Use a restrained 16:9 canvas with four KPI cards: Total Orders, Total Payment Value, Average Order Value, and Customer Count. Add:

- monthly Total Orders columns with a Total Payment Value line;
- order-status distribution;
- orders by delivery state;
- top ten categories by Item Merchandise Value.

Show the subtitle “Tendered payment value; not accounting revenue” below the payment card. Synchronize purchase date and order status. Keep the category slicer scoped to item/category visuals.

### Operations & Data Quality

Separate the page visually into two sections. Business operations contains Delivered Orders, Late Deliveries, On-time Delivery Rate, Average Delivery Days, a seller matrix using item-safe measures, and top categories by distinct late orders. Pipeline health contains current run status and version, accepted/rejected rows, quality outcomes, freshness, a per-source freshness table, and run outcomes/retries.

Date/status/category slicers affect the business section only. Pipeline tables are disconnected and current health cards do not respond to run-chart selections. The exact layout and interaction contract is in `power_bi/report_spec.yaml`.

## Reproducible PBIP/TMDL project

The generated source is under `power_bi/OlistELTReporting/`:

- `OlistELTReporting.pbip` is the supported project entry point.
- `OlistELTReporting.SemanticModel/definition/` contains TMDL for 14 imported views plus the dedicated `Measures` home table.
- `OlistELTReporting.Report/definition/` contains enhanced PBIR metadata and blank `Executive Overview` and `Operations & Data Quality` page shells.
- `scripts/build_power_bi_project.py` deterministically regenerates these files from the repository contract. Run `make power-bi-project`; it does not connect to Snowflake or persist credentials.

The `SnowflakeServer` parameter is intentionally `SET_IN_POWER_BI_DESKTOP`. `SnowflakeWarehouse`, `SnowflakeDatabase`, and `SnowflakeRole` contain non-secret defaults. The Import partitions use `Snowflake.Databases` with connector implementation 2.0 and retain credentials outside project source.

## Open and finish in Power BI Desktop

These steps require a current Power BI Desktop installation on Windows or an authorized Fabric authoring workspace.

1. Back up and close the existing manually created PBIX. The repository project is separate and does not overwrite it.
2. On Windows, clone/copy the repository to a normal local path and open `power_bi/OlistELTReporting/OlistELTReporting.pbip` in a current Power BI Desktop. Do not open an individual TMDL file as the report.
3. In **Transform data → Edit parameters**, replace `SnowflakeServer` with the approved Snowflake server/account host. Leave the documented warehouse/database/role defaults unless your approved environment differs.
4. In **Data source settings**, authenticate through the supported Snowflake connector flow. Never paste credentials, tokens, or private-key contents into tracked project files.
5. Refresh. Confirm 14 imported source tables plus the disconnected Measures table, 10 active and two inactive relationships, Date marked with `DATE_DAY`, two calculated Date columns, and 41 measures.
6. Build visuals on the two existing blank pages from `power_bi/report_spec.yaml`. The semantic model is ready; visual JSON was deliberately not fabricated.
7. Configure the documented slicers and interactions. Category/seller visuals must use item-safe measures and must not allocate order-level payments across items. Pipeline-health tables remain disconnected from business slicers.
8. Compare every unfiltered KPI and each monthly row with `sql/power_bi/002_validation_queries.sql` and `reports/power_bi_backend_validation.json`.
9. Test date and status filters, seller/category interactions, inactive-date behavior where used, operational-table isolation, and filtered totals.
10. Save the PBIP from Desktop. Confirm `.pbi/localSettings.json`, `.pbi/cache.abf`, and any credential-bearing local state remain ignored.
11. Capture genuine screenshots of Executive Overview, Operations & Data Quality, Model view, and reconciliation evidence under `docs/screenshots/`, with connection identifiers redacted.
12. Re-run repository tests and secret checks. Only then may Milestone 9 be marked Completed and validated and committed as `feat: add Power BI reporting dashboard`.

Official references: [connect Power BI to Snowflake](https://learn.microsoft.com/en-us/power-bi/connect-data/service-connect-snowflake) and [Power BI Desktop projects](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview).

## Validation boundary and limitations

The three operational views and all documented backend totals were executed against real Snowflake on 2026-10-19. Their current freshness state is a live age calculation, so it will change without a new load. The latest validated publication timestamp remains 2026-10-16.

The PBIP/TMDL source artifact and two empty report-page definitions exist and pass structural/parser validation. Power BI Desktop is unavailable on this macOS host, so open/import, refresh, rendered visuals, relationship behavior, slicer interactions, filtered totals, and screenshots remain unverified. Those UI/runtime checks are mandatory; structural validity and backend agreement do not complete the milestone.
