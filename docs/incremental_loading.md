# Incremental ELT and idempotency

Status: **Completed and validated** against real Snowflake on 2026-10-15. Aggregate evidence, including every batch ID/count/timing and comparison result, is in [incremental_validation.json](../reports/incremental_validation.json).

## Coverage audit

Milestones 2–5 already validated deterministic manifests and S3 keys, immutable-object checksums, manifest-last upload, batch/file/row reconciliation, identical-load skips, four keyed dbt merges, and the full quality suite. These mechanisms remain in use.

The unproven cases were sequential evolution through all historical windows, changed records, old business events arriving later, out-of-order delivery, failure after a real COPY, and equivalence to a full refresh. Milestone 6 adds an isolated replay harness and closes two implementation gaps: the append loader rejects overlapping natural keys before commit, and dbt compares candidate rows with the existing fact instead of relying on a global timestamp cutoff.

## Incremental contract

| Case/layer | Identity and behavior |
|---|---|
| Initial historical load | Load the reference snapshot, then deterministic nonempty monthly transaction windows |
| Subsequent loads | Append a new manifest batch atomically; build the same dbt graph after each window |
| S3 file identity | Object path plus immutable SHA-256 and byte count; matching files skip, differing content at the same key fails |
| Manifest identity | Content-derived batch ID covers source version, contract version, window, and file metadata |
| Duplicate file entry | Reject duplicate relative paths or multiple files for a table under manifest contract v1 |
| RAW batch identity | Successful reconciled batch ID plus actual RAW counts permits skip; uncommitted rows fail closed |
| RAW business identity | Repeated declared natural keys in a new append batch cause rollback; geography and review IDs do not have false uniqueness assumptions imposed |
| Changed existing records | Immutable historical RAW batches are not a CDC feed. A correction requires an explicitly approved source snapshot replacement/correction. Given a corrected source relation, keyed fact merges replace its current analytical row |
| dbt candidate identity | Full projected row comparison selects new/changed candidates; deterministic surrogate keys control merge targets |
| Unchanged dbt execution | Candidate set is empty, producing zero inserted/updated fact rows |
| Late/out-of-order arrival | Business dates do not gate processing. New or changed candidates are evaluated regardless of the business date or a global ingestion watermark |
| Freshness | Actual RAW `_loaded_at`; never historical purchase, shipping, review, or logical replay dates |
| Failure | Roll back RAW and file-success records together; commit FAILED batch/run evidence separately |
| Recovery | Retry the same manifest through the existing loader; append once and retain FAILED → SUCCEEDED audit history |

The current contract is serialized execution by one writer. Concurrent writers are not protected by enforced Snowflake unique constraints and are outside this validation. Deletions require a separately approved full refresh or explicit deletion policy; ordinary merges do not infer tombstones. Review facts use full-record identity because `review_id` is nonunique: an edited review is a distinct record unless an upstream correction contract supplies a stable identity.

## Replay and isolation

`python -m olist_pipeline.incremental` reuses `WarehouseLoader`, `SnowflakeBackend`, the nine source contracts, canonical manifests, the existing external stage/file format, and the real dbt project. There is no second batch-state system: the existing four audit table definitions and reconciliation view are reproduced under the test prefix. A local checkpoint records evidence and resume position only.

The service role cannot create schemas. Each run therefore owns explicitly named `M6_<12 uppercase hexadecimal characters>_` tables/views in the existing five schemas. Production relations are read only. The dbt alias macro and source identifiers select the same prefix, while an empty prefix retains ordinary production behavior. No warehouse, database, schema, stage, storage integration, IAM object, or S3 data is provisioned or changed.

The sequence is the reference snapshot plus 25 historical transaction months. One adjacent pair of months is deliberately delivered out of order to test arrival independence. This is deterministic replay of a fixed Olist snapshot, not streaming or a claim about real arrival history. Each step records its batch ID, business window, files, represented rows, inserted/updated/skipped/rejected rows, elapsed time, and reconciliation difference.

## Change and late-arrival scenarios

After historical convergence, the harness copies one existing item into an isolated fixture table. It changes that item's price by R$1.00 only in the isolated RAW copy, deliberately retains its earlier ingestion timestamp, builds dbt, checks the detail/order targets and monetary delta, reruns, and compares all 24 models with a full refresh. This challenges the previous global-watermark assumption directly. It restores the original value afterward.

A separate scenario adds one item component to an old order, retaining the old shipping date while using a current ingestion timestamp. Its R$12.34 merchandise and R$1.23 freight contributions must appear exactly once in the detail and order aggregates. A rerun and full refresh must converge. The harness then removes only that test component and its isolated fact; production is never changed.

The raw append contract deliberately rejects an overlapping source business key. The isolated changed-record scenario demonstrates transformation update semantics, not automatic CDC support in the immutable file loader.

## Interruption and recovery

The injected exception occurs immediately after the first real COPY and its file-success audit insertion, within the normal batch transaction. The loader's existing rollback must leave zero committed RAW rows and zero successful file records for the failed batch. The same batch then recovers using the normal loader, retaining both failed and successful attempts. This exercises application failure after partial progress; process termination, network loss during COMMIT, and concurrent writers are not claimed.

## Full-refresh comparison

At final historical state, RAW business values and multiplicities are compared against the validated complete production snapshot. Copies of all 24 incremental model results are then compared with the same project's full refresh over the identical isolated RAW data. Bidirectional SQL set differences include grouped multiplicities, row counts, and all business columns; operational `source_*` metadata is excluded. The normal dbt suite independently checks grains, relationships, and monetary reconciliation.

Candidate comparison scans the source-derived facts before merging changes. For this small fixed snapshot this trades scan cost for correctness without an unbounded timestamp lookback. It is not a claim that this strategy outperforms CDC or partition pruning at large scale. Recorded timings include network and warehouse startup variation.

## Measured replay and scenario results — 2026-10-15

The real Snowflake replay processed 26 batches / 129 files / 1,550,922 RAW rows. Every batch had zero reconciliation difference; historical RAW updates and rejected rows were zero. The reference snapshot inserted 1,036,280 rows from four files in 22.712 seconds. The 25 transaction windows each ran the complete dbt graph. January 2017 was deliberately delivered before December 2016; the deferred December batch still inserted its five source rows and four fact rows.

| Scenario | Actual result |
|---|---|
| Sequential historical facts | 415,201 fact rows inserted across transaction builds |
| Duplicate final batch | 0 inserted/updated, 16 rows and 5 files skipped; 3.145 seconds |
| Unchanged dbt rerun | 0 fact inserts/updates/deletes; 28.540 seconds |
| Controlled price correction | Exactly 1 isolated RAW row changed; 0 fact inserts and 2 updates; merchandise +R$1.00 |
| Correction rerun/full refresh | 0 further fact writes; all 24 model business fingerprints equal the full refresh |
| Late item | Business timestamp 3,678 days earlier; 1 fact inserted, 1 order updated; merchandise +R$12.34 and freight +R$1.23 |
| Late-item rerun/full refresh | 0 further fact writes; all 24 model business fingerprints equal the full refresh; 9/9 freshness checks pass |
| Duplicate business key | Rejected inside the isolated append transaction; 0 committed rows |
| Interrupted October 2016 batch | Exception after first real COPY/audit insertion; 0 committed rows/files; FAILED recorded; 13.090 seconds |
| Recovery of the same batch | 5 files / 1,674 rows committed exactly once; FAILED → SUCCEEDED; 17.072 seconds |

Successful RAW load durations sum to 528.900 seconds, excluding dbt and the failed attempt. Individual successful batches took 17.072–23.596 seconds. These observations include network/warehouse variation and do not establish a general speedup. The correction full refresh took 25.714 seconds; the late-item full refresh took 21.349 seconds. Full-refresh adapter `rows_inserted` counts describe newly created tables, not incremental merge activity.

After scenario restoration, the order metric totals are 99,441 orders, merchandise R$13,591,643.70, freight R$2,251,909.54, and payments R$16,008,872.12. Genuine carrier-before-purchase anomalies remain 166; synthetic corrections and late items do not replace or repair them.

The final historical full refresh completed in 21.814 seconds. Exact grouped-value/multiplicity comparisons found zero row-count and business-record differences across nine RAW datasets and all 24 dbt models. Both results contain 415,201 fact rows and 251,987 dimension rows (667,188 marts total). Each full-data build reported 24 successful models, 156 passing tests, one deliberate source warning, and zero failures/skips. The final production standalone test run reported 156 pass / 1 warning in 16.876 seconds; production freshness passed 9/9 in 2.708 seconds at a measured maximum age of 104 hours.

The isolated final suite reported 156 pass / 1 warning in 9.486 seconds and freshness 9/9 in 3.880 seconds. A direct duplicate file COPY inserted zero rows and left the file row count unchanged. Production RAW/MARTS count-and-content fingerprints were unchanged; production reconciliation still had zero differences and zero synthetic-prefix records. The repository suite discovered 30 tests: 29 passed and only the separately validated AWS integration was skipped (14.646 seconds). Earlier real S3 duplicate-upload evidence is reused explicitly, not represented as a new AWS upload run.

Cleanup removed all 63 explicitly recorded test relations and verified zero remaining relations under the run prefix. These disposable copies can be recreated by replay; aggregate evidence remains versioned. Production tables and S3 objects were not deleted.

## Reproduction and cleanup

Load the ignored local environment and use the existing approved credential chain:

```bash
export OLIST_RUN_SNOWFLAKE_INTEGRATION=1
PYTHONPATH=src python -m olist_pipeline.incremental --prefix M6_0123456789AB_ --phase replay
PYTHONPATH=src python -m olist_pipeline.incremental --prefix M6_0123456789AB_ --phase scenarios
PYTHONPATH=src python -m olist_pipeline.incremental --prefix M6_0123456789AB_ --phase convergence
PYTHONPATH=src python -m olist_pipeline.incremental --prefix M6_0123456789AB_ --phase finish
PYTHONPATH=src python -m olist_pipeline.incremental --prefix M6_0123456789AB_ --phase cleanup
```

Choose a fresh prefix per independent run. Replay can resume from its ignored checkpoint. Scenario and convergence phases must be inspected before retrying a partially failed phase; they intentionally do not silently replace existing fixtures. Evidence/logs/profiles/catalogs live in ignored `data/processed/incremental/<prefix>/`. Cleanup drops only the explicit relations recorded as created by that run, after prefix validation; it never drops schemas or uses wildcard deletion. Preserve aggregate evidence before cleanup.
