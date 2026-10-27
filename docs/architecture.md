# Architecture

## Target flow

```mermaid
flowchart TB
    subgraph Source
      A["Official Olist CSV snapshot"]
    end
    subgraph Ingestion
      B["Python contract validation"]
      C["Immutable manifest + SHA-256"]
    end
    subgraph AWS
      D["S3 raw/version/table/batch_id/file.csv"]
    end
    subgraph Snowflake
      E["RAW: source rows + load metadata"]
      F["STAGING: typed, renamed, tested"]
      G["INTERMEDIATE: dedupe, aggregate, reconcile"]
      H["MARTS: dimensional reporting models"]
      I["AUDIT: runs, files, counts, tests, exceptions"]
    end
    J["Power BI semantic model"]
    K["Airflow scheduler and recovery"]

    A --> B --> C --> D --> E --> F --> G --> H --> J
    K -. coordinates .-> B
    K -. coordinates .-> E
    K -. coordinates .-> H
    B --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

Milestone 2's S3 layer is populated and validated with 26 immutable batches and 155 objects. Milestone 3 loaded and reconciled all 1,550,922 source rows into Snowflake RAW. Milestone 4 built the complete 24-model dbt DAG in Snowflake: 9 staging views, 4 intermediate views, 7 dimensions, and 4 facts. Milestone 5 added load-timestamp freshness, audit/row reconciliation, 157 dbt tests, and isolated temporary-table failure injection without changing production data. Milestones 6–8 validated replay, idempotency, Airflow publication gates, monitoring, rollback, and recovery. Milestone 9 validated the 15-table Power BI model and two-page report in Desktop.

## Snowflake organization

Deployed database: `OLIST_ELT`.

| Schema | Responsibility | Mutation policy |
|---|---|---|
| `RAW` | Source-shaped tables plus `_batch_id`, `_source_file`, `_file_sha256`, `_loaded_at` | Append immutable batches; no business cleanup |
| `STAGING` | Cast types, normalize names, standardize empty strings, expose source keys and lineage | Nine dbt views derived one-to-one from RAW sources |
| `INTERMEDIATE` | Deduplicate geography and build independent item/payment order aggregates | Four rebuildable dbt views |
| `MARTS` | Seven dimensions and four conformed facts | Dimensions rebuild as tables; transaction facts merge incrementally |
| `AUDIT` | Batch manifests, task/run status, row counts, test outcomes, exceptions, publication state | Append events; controlled status transitions |

Quality controls read `AUDIT.BATCH_RECONCILIATION` and RAW `_loaded_at`. Freshness therefore measures real warehouse load activity rather than historical order events or deterministic replay dates. Synthetic failure probes use session-scoped temporary tables in `AUDIT`; they fingerprint but never mutate production RAW or MARTS relations.

The RAW layer stores source fields as `VARCHAR` so ingestion does not silently coerce source values. Each row also carries batch ID, staged filename, artifact checksum, source version, logical ingestion date, staged row number, load run ID, and load timestamp. Typing belongs in STAGING.

The `OLIST_ELT_ROLE` service role performs RAW loading, transformations, and orchestration publication through key-pair authentication in the existing schemas. S3 access uses the pre-provisioned storage integration. The role cannot create databases or schemas. A separate read-only BI consumer role remains a future setup task.

## Batch identity and deterministic replay

The public dataset is a fixed snapshot, not an event feed. Historical simulation therefore uses deterministic logical windows rather than pretending files arrived on dates they did not.

1. Hash each untouched source file with SHA-256 and record its byte size, row count, and source version in a manifest.
2. Define half-open monthly windows `[window_start, window_end)` over `orders.order_purchase_timestamp`. Only the 25 nonempty months are emitted.
3. Assign customers, order items, payments, and reviews to the window of their parent order. Load product, seller, category, and geography tables once in a separate reference snapshot under the same source version.
4. Derive `batch_id = sha256(source_version | manifest_hash | window_start | window_end | pipeline_contract_version)`.
5. Write immutable S3 keys containing source, logical ingestion date, batch ID, and table. Never overwrite a different checksum at an existing key.
6. Upload data objects first and the manifest last as the batch commit marker. A retry with the same checksum validates and skips objects; a checksum conflict fails closed. `AUDIT.FILE_LOADS` records enforce the same invariant in Snowflake.
7. Validate each staged CSV, then `COPY` into RAW inside the batch transaction. Reconcile actual rows and reject overlapping declared natural keys before committing RAW and file-success audit records together. Publish marts only after all tasks and blocking tests pass.
8. dbt incremental facts compare projected candidate rows with current fact rows, then merge only new or changed rows using declared surrogate unique keys. This avoids missing changes behind a global timestamp watermark. A full refresh uses the same transformations. Airflow validates the complete deterministic batch inventory on each run; its wall-clock schedule does not change historical content keys or filter business dates.

This permits chronological demos, reruns, isolated backfills, and failure injection without changing source truth. Late-arriving behavior is tested synthetically and labeled as such because the snapshot has no ingestion-arrival timestamps.

Milestone 6's validation harness uses explicitly prefixed copies in the existing schemas, the original S3 stage, the same loader/audit definitions, and the same dbt project. It does not require schema-creation privileges. Prefix isolation applies to model aliases and source identifiers together; it is absent during normal production execution. See [incremental loading](incremental_loading.md) for the correction contract, serialized-writer limitation, and replay evidence.

## Failure and publication boundaries

Milestone 7 adds a Dockerized Airflow LocalExecutor deployment coordinating the existing package boundaries. Run-specific dbt model aliases build from shared validated RAW. Eleven immutable reporting stores and stable `REPORT_*` views use one transactional `AUDIT.REPORTING_CURRENT` pointer; publication and version history commit only after all quality gates pass. This protects the prior reporting state from partial model builds and failed checks. See [orchestration](orchestration.md) for task contracts, concurrency limits and multi-query snapshot considerations.

Milestone 8 extends those same task-attempt events with versioned operational observations and derives run-level summaries from existing audit/publication records. Accepted, rejected, held, and inserted rows have separate meanings; synthetic quarantine is isolated in session temporary tables. No second run ledger or external monitoring service is introduced. See [monitoring and recovery](monitoring_recovery.md).

- Download or checksum failure: no manifest is finalized.
- Partial S3 upload: the batch stays uncommitted and is safe to retry.
- Snowflake validation failure: landing data is discarded; previously loaded RAW data remains.
- CSV pre-validation failure: rejected-record details are written to `AUDIT.LOAD_ERRORS`; no RAW COPY begins.
- COPY or row-count mismatch: the current batch transaction rolls back and a failed batch audit record is committed separately.
- dbt compile/build/test or reconciliation failure: reporting views are not advanced to the candidate build.
- Power BI consumers use only the last validated reporting views. The source-controlled PBIP/TMDL model and 33 PBIR visuals were refreshed and interaction-tested in Power BI Desktop; the three committed screenshots contain no connection identifiers.
- Every retry reuses the same Airflow run ID, candidate prefix, and deterministic source batch IDs.

## Dimensional model

```mermaid
erDiagram
    DIM_CUSTOMER ||--o{ FCT_ORDERS : places
    DIM_ORDER_CUSTOMER ||--o{ FCT_ORDERS : ships_to
    DIM_DATE ||--o{ FCT_ORDERS : purchase_date
    FCT_ORDERS ||--o{ FCT_ORDER_ITEMS : contains
    FCT_ORDERS ||--o{ FCT_ORDER_PAYMENTS : paid_by
    FCT_ORDERS ||--o{ FCT_ORDER_REVIEWS : reviewed_by
    DIM_PRODUCT ||--o{ FCT_ORDER_ITEMS : describes
    DIM_SELLER ||--o{ FCT_ORDER_ITEMS : fulfills
    DIM_CATEGORY ||--o{ DIM_PRODUCT : classifies
    DIM_GEOGRAPHY ||--o{ DIM_ORDER_CUSTOMER : locates
    DIM_GEOGRAPHY ||--o{ DIM_SELLER : locates
```

`DIM_CUSTOMER` represents a person-level `customer_unique_id`; `DIM_ORDER_CUSTOMER` preserves each order-specific `customer_id` and its delivery location. This avoids falsely treating repeat purchases as different people while retaining historical order geography.

## Monetary safety

Items and payments are both one-to-many children of orders. Directly joining them creates a many-to-many fanout. The model will:

```sql
-- conceptual only
item_totals    = group order_items by order_id
payment_totals = group order_payments by order_id
orders         = orders left join item_totals left join payment_totals
```

`item_merchandise_value`, `freight_value`, `item_total_value`, and `payment_total_value` remain separate measures. Differences are surfaced, not forced to zero. “Revenue” is intentionally avoided because the dataset does not expose commission, refunds, taxes, seller payouts, or accounting recognition.

## Power BI consumer boundary

Eleven stable `MARTS.REPORT_*` views preserve the published dimensional grains. Power BI uses Report Orders for order/payment KPIs and Report Order Items for seller/product/category analysis; distinct-order `TREATAS` measures carry an item selection to delivery KPIs without a bidirectional relationship or item/payment fanout. Three narrow `AUDIT.PBI_*` views expose run, freshness, quality, accepted/rejected, and publication state. These operational tables are disconnected from business dimensions so a category or date selection cannot rewrite the meaning of current pipeline health.

The source-controlled PBIP links an enhanced PBIR report folder to a TMDL semantic-model folder by relative path. Four Power Query parameters configure the Snowflake Import partitions; only the server placeholder requires local input and authentication remains in Desktop's external credential store. The semantic model is reproducible independently of Desktop-local caches.

```mermaid
flowchart LR
    P["AUDIT.REPORTING_CURRENT"] --> V["11 MARTS.REPORT_* views"]
    V --> B["Power BI business model"]
    A["Existing AUDIT events/reconciliation"] --> O["3 AUDIT.PBI_* views"]
    O --> H["Power BI health model"]
    B -. disconnected .- H
```

The model, DAX, two-page visual definitions, and screenshots are source-controlled. Reproduction still requires a local approved Snowflake connection in Power BI Desktop because the tracked server parameter is deliberately scrubbed. This boundary is detailed in [dashboard](dashboard.md).

## Resource and cleanup estimate

The validated S3 prefix contains 124,509,854 bytes across 155 objects. Snowflake RAW contains 1,550,922 rows in nine tables and MARTS contains 667,188 rows in 11 relations, built by an X-Small warehouse with a 60-second auto-suspend. Cleanup must remove only explicitly approved project objects, including versioned S3 objects where applicable, and must occur only after evidence is retained and deletion is authorized.
