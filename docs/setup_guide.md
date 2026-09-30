# Setup guide

## Prerequisites

- Python 3.9 or newer.
- Git and Make.
- Internet access to Kaggle's public dataset endpoint.
- Approximately 170 MB free disk space during download and extraction.

Cloud accounts and credentials are not required for Milestone 1 or local Milestone 2 validation.

## Bootstrap

```bash
git clone <repository-url>
cd orchestrated-elt-data-quality-pipeline
cp .env.example .env
make download
make test
make profile
make validate
make ingest-local
make warehouse-validate
```

The public API download currently requires no Kaggle credentials. If Kaggle changes that policy, install/configure its CLI without committing `~/.kaggle/kaggle.json`, then place the official nine CSVs directly in `data/raw/`.

## Optional virtual environment

The Milestone 1 and local ingestion commands have no third-party runtime dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Credentialed S3 integration can install `.[cloud]`. dbt, Airflow, and Docker dependencies will be introduced in their own milestones with compatible version constraints; they are intentionally absent now.

## Commands

| Command | Purpose | Writes |
|---|---|---|
| `make download` | Download and safely extract the official ZIP | Ignored `data/raw/*.csv` |
| `make test` | Run offline unit tests | Python cache only |
| `make profile` | Recompute aggregate evidence | `reports/data_profile.json` |
| `make validate` | Validate all rows, contracts, keys, and FKs | Console only |
| `make ingest-local` | Build deterministic batches and upload to the local S3 substitute | Ignored `data/processed/` |
| `make warehouse-validate` | Render all infrastructure/COPY plans and reconcile every manifest locally | Console only |
| `make clean` | Remove Python bytecode caches | Cache directories only |

## Configuration and secrets

`.env.example` documents variable names only. Copy it to ignored `.env` for local use. Prefer AWS profiles or workload identity and Snowflake key-pair/OAuth authentication. Never add access keys, passwords, private keys, account exports, raw CSVs, or customer/order identifiers to commits, logs, screenshots, or issue descriptions.

## Optional approved AWS execution

Install the cloud dependency group and use the standard AWS SDK credential chain. Do not place keys in `.env`.

```bash
python -m pip install -e '.[cloud]'
export AWS_PROFILE='<approved-profile>'
export AWS_REGION='us-east-1'
export S3_BUCKET='<approved-existing-bucket>'
PYTHONPATH=src python -m olist_pipeline.ingestion --backend s3
```

To run the self-cleaning integration test against that approved prefix, additionally export `OLIST_RUN_AWS_INTEGRATION=1` and run `make test`. Keep it unset for normal tests.

## Optional approved Snowflake execution

Milestone 3 requires an existing warehouse, least-privilege role/user, key-pair authentication, an existing S3 storage integration, and the actual Milestone 2 objects in the configured bucket/prefix. After approval, install `.[cloud]`, export the variables documented in `.env.example`, and explicitly opt in:

```bash
export OLIST_RUN_SNOWFLAKE_INTEGRATION=1
PYTHONPATH=src python -m olist_pipeline.warehouse bootstrap
PYTHONPATH=src python -m olist_pipeline.warehouse load
PYTHONPATH=src python -m olist_pipeline.warehouse validate-remote
```

`bootstrap` can create the configured database/schemas and therefore must not be run against an unapproved account. The project never creates storage integrations or alters AWS IAM.

## Updating the source snapshot

Do not overwrite evidence silently. Download to a new source-version location in the future, compare SHA-256 hashes and schemas, rerun profiling/validation, document changes, and assign a new manifest/source version. The committed profile describes the hashes downloaded on 2026-09-29.
