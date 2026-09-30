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
