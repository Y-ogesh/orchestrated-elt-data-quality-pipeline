# Engineering decisions

## ADR-001 — Preserve raw files outside Git

**Status:** Accepted, 2026-09-29

Raw CSVs contain row-level customer and transaction data and total roughly 126 MB extracted. They are downloaded from the attributed source, stored under ignored `data/raw/`, hashed, and never committed. Only aggregate profiling evidence is versioned.

## ADR-002 — Standard-library Milestone 1 tooling

**Status:** Accepted, 2026-09-29

The baseline machine has Python 3.9.6 but not pytest, boto3, or the Snowflake connector. Acquisition, profiling, validation, and unit tests use the standard library so the foundation runs immediately. Optional `dev` and `cloud` dependency groups declare future tools without making this milestone depend on cloud packages.

## ADR-003 — Keep independent monetary grains

**Status:** Accepted, 2026-09-29

Order items and payments are separate one-to-many relationships. Each is aggregated to order grain before joining. Item merchandise, freight, payment total, and reconciliation difference remain separate; no generic `revenue` measure is inferred.

## ADR-004 — Model both customer identities

**Status:** Accepted, 2026-09-29

`customer_id` is unique per order while `customer_unique_id` identifies repeat purchasers. `dim_customer` uses the latter grain; `dim_order_customer` preserves the former and its order-time delivery geography.

## ADR-005 — Review identifier is not a primary key

**Status:** Accepted, 2026-09-29

The snapshot has 99,224 review rows but only 98,410 distinct review IDs. Review models use a deterministic full-record hash and treat exact duplicate future records as exceptions rather than silently losing them.

## ADR-006 — Replay fixed snapshots with logical purchase windows

**Status:** Accepted, 2026-09-29

Because the dataset does not expose ingestion arrival times, historical batches use monthly order-purchase windows. Child facts inherit the parent order window, batch IDs derive from the manifest and window, and reference tables remain versioned snapshots. This is reproducible and does not fabricate an arrival history.

## ADR-007 — Preserve RAW and gate publication

**Status:** Accepted, 2026-09-29

Quality issues are recorded, not edited in RAW. Typed staging, exception flags, and deterministic reductions happen downstream. A candidate reporting build becomes visible only when required loads, reconciliations, and tests pass, preserving the last validated publication on failure.

## ADR-008 — Use a manifest-last commit protocol

**Status:** Accepted, 2026-09-30

Data objects are uploaded and verified before `manifest.json`. The manifest acts as the immutable batch commit marker. A committed batch is accepted only if every object still matches its manifest metadata; partial attempts can safely resume, and checksum conflicts fail rather than overwrite.

## ADR-009 — Treat ingestion dates as logical replay dates

**Status:** Accepted, 2026-09-30

The public snapshot has no arrival timestamps. Monthly transaction batches use the exclusive window end as `logical_ingestion_date`; the reference snapshot uses the published source date. Actual execution time appears in structured logs, not the content identity, so rebuilding on another day produces the same batch IDs and keys.

## ADR-010 — Preserve source values as VARCHAR in RAW

**Status:** Accepted, 2026-09-30

All source fields load into RAW as `VARCHAR`; source spelling and null behavior remain observable, while lineage metadata is added in separate columns. Casting, renaming, and business rules belong in STAGING so malformed values cannot be silently coerced during ingestion.

## ADR-011 — Pre-validate before metadata-enriched COPY

**Status:** Accepted, 2026-09-30

Snowflake validation mode does not support transformed COPY statements. Each staged CSV is therefore validated first against a temporary source-shaped table with `RETURN_ALL_ERRORS`. Only error-free files enter the transactional COPY that adds metadata. Rejected records are audited, and any COPY/count mismatch rolls back the complete batch.

## ADR-012 — Increment transaction facts, rebuild dimensions

**Status:** Accepted, 2026-09-30

The four transaction facts use merge-based incremental materializations keyed by deterministic SHA-256 surrogates and a `source_loaded_at` overlap. The seven dimensions rebuild as tables because the fixed source snapshot is small and a full deterministic rebuild is simpler than maintaining unnecessary slowly changing state.

The timestamp-only candidate selection in this decision is superseded by ADR-018. The stable keys, merge materialization, and dimension rebuild policy remain unchanged.

## ADR-013 — Use environment-isolated dbt schemas

**Status:** Accepted, 2026-09-30

Production models resolve to `STAGING`, `INTERMEDIATE`, and `MARTS`. Development models resolve to `<DBT_DEV_SCHEMA>_<layer>` through a controlled schema-name macro. This prevents one developer's run from replacing governed relations while keeping lineage names readable. Profile credentials remain external environment values and private-key passphrases use dbt's secret environment prefix.

## ADR-014 — Pre-provision Snowflake control-plane objects

**Status:** Accepted, 2026-10-11

The application service role must not hold account-level `CREATE DATABASE` or database-level `CREATE SCHEMA` privileges. Administrators pre-provision the database, five schemas, storage integration, external stage, service user, role, and warehouse. Bootstrap validates those prerequisites—including stage URL, integration, and object access—then creates or reuses only the project file format, RAW/audit tables, and views. This preserves least privilege and prevents the loader from becoming a competing infrastructure-management path.

## ADR-015 — Preserve known timestamp anomalies with explicit warning severity

**Status:** Accepted, 2026-10-11

The source contains 166 orders whose carrier timestamp precedes purchase. The pipeline retains these values and exposes them through a warning-level dbt test instead of rewriting source truth or weakening unrelated date rules. Approval, customer-delivery, estimated-delivery, and review-answer chronology remain blocking tests because the validated source has zero violations for those rules.

## ADR-016 — Measure pipeline freshness from RAW load time

**Status:** Accepted, 2026-10-14

Source freshness uses the maximum RAW `_loaded_at` timestamp, warns after 7 days, and errors after 30 days. Historical Olist business timestamps and deterministic logical ingestion dates do not measure pipeline operation. The thresholds match a weekly validation cadence while allowing a fixed public snapshot to remain semantically historical.

## ADR-017 — Inject quality failures only in session temporary tables

**Status:** Accepted, 2026-10-14

Synthetic defects execute in Snowflake temporary tables within the approved `AUDIT` schema. The cycle proves a clean baseline, exact detection, correction, and recovery, then compares production RAW/MARTS fingerprints and reserved-prefix counts. This provides real-engine behavior without corrupting or requiring cleanup of validated production tables.

## ADR-018 — Select changed fact rows without a global timestamp cutoff

**Status:** Accepted, 2026-10-15

Compare the complete projected fact candidate row with the current target before merging. A global maximum ingestion timestamp can omit late-visible rows or changes to resolved relationships. Evaluating the source-derived candidate relation and merging its set difference provides deterministic insert/update semantics and zero writes on an unchanged rerun. This scans more input than watermark pruning; scaling beyond this snapshot requires measured partitioning or an explicit CDC/change ledger. Stable business keys and upstream uniqueness tests remain mandatory. Review full-record identity and deletion limitations remain explicit.

## ADR-019 — Preserve immutable RAW append and isolate correction demonstrations

**Status:** Accepted, 2026-10-15

The historical file loader rejects overlapping declared natural keys inside its batch transaction; it does not silently upsert source truth. Changed-record demonstrations apply corrections to explicitly isolated source copies and prove downstream merge behavior. Production corrections require an approved source replacement/correction process. No automatic CDC, last-write-wins version resolver, deletion propagation, or concurrent-writer locking is claimed.

## ADR-020 — Reuse existing schemas for multi-session replay isolation

**Status:** Accepted, 2026-10-15

The application role cannot create schemas. Multi-session dbt replay therefore uses uniquely prefixed tables/views inside existing schemas, preserving the stage and file format. The harness reuses loader classes and audit definitions, fingerprints production data, and records exact created objects for scoped cleanup. No account-level privilege is added.

## ADR-021 — LocalExecutor and separate dependency environments

**Status:** Accepted, 2026-10-16

Use pinned Airflow 3.3.2 with PostgreSQL, API server, scheduler, and DAG processor. LocalExecutor avoids unnecessary brokers/workers for a serialized portfolio workload. Keep dbt/AWS/Snowflake in a separate locked Python environment inside the same image. Only dependency files enter the build context; code and secret configuration are mounted at runtime. This is not an HA/multi-user production deployment.

## ADR-022 — Publish immutable mart versions through one transactional pointer

**Status:** Accepted, 2026-10-16

Run-specific dbt aliases isolate candidate builds without schema-creation privileges. After all existing gates pass, copy the eleven candidate marts into versioned stores and atomically change a singleton reporting pointer in the same transaction as publication history. Stable reporting views never depend on partially built candidates. Retain previous versions; incompatible schema migrations and retention deletion require explicit decisions. Multi-query consumers must pin a version if they require snapshot consistency across separate statements.

## ADR-023 — Serialize writers and preserve failure in the audit leaf

**Status:** Accepted, 2026-10-16

One active DAG run, one active task, and a one-slot writer pool enforce the existing serialized-writer contract inside this deployment. External manual writers are prohibited while the DAG runs; no distributed cross-deployment lock is claimed. An `all_done` audit task must fail when any required ancestor failed or never executed, otherwise Airflow can treat a successful audit leaf as a successful DAG despite upstream failure. The existing load audit remains authoritative; a narrow task-attempt table adds orchestration metadata only.
