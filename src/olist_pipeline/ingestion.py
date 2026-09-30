"""Build deterministic Olist batches and upload them idempotently."""

import argparse
import csv
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .dataset import TABLES
from .manifest import BatchManifest, ManifestFile, sha256_file
from .storage import (
    LocalObjectStore,
    ObjectConflictError,
    ObjectNotFoundError,
    ObjectStore,
    S3ObjectStore,
    with_retry,
)


LOGGER = logging.getLogger("olist_pipeline.ingestion")
SOURCE = "olist"
DEFAULT_SOURCE_VERSION = "kaggle-v2-2021-10-01"
CONTRACT_VERSION = "1"
TRANSACTION_TABLES = ("orders", "customers", "order_items", "order_payments", "order_reviews")
REFERENCE_TABLES = ("products", "sellers", "geolocation", "category_translation")


def _log(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, sort_keys=True))


def _month_bounds(month: str) -> Tuple[str, str, str]:
    year, month_number = (int(value) for value in month.split("-"))
    start = date(year, month_number, 1)
    if month_number == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month_number + 1, 1)
    return (
        start.isoformat() + "T00:00:00Z",
        end.isoformat() + "T00:00:00Z",
        end.isoformat(),
    )


def _count_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def _source_metadata(data_dir: Path) -> Dict[str, Tuple[str, int]]:
    return {
        name: (sha256_file(data_dir / contract.filename), _count_rows(data_dir / contract.filename))
        for name, contract in TABLES.items()
    }


def _write_filtered_csv(
    source: Path,
    destination: Path,
    predicate: object,
) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with source.open(newline="", encoding="utf-8-sig") as input_stream, destination.open(
        "w", newline="", encoding="utf-8"
    ) as output_stream:
        reader = csv.DictReader(input_stream)
        writer = csv.DictWriter(output_stream, fieldnames=reader.fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            if predicate(row):
                writer.writerow(row)
                count += 1
    return count


def _manifest_file(
    *,
    table: str,
    path: Path,
    row_count: int,
    source_sha256: str,
    source_row_count: int,
) -> ManifestFile:
    return ManifestFile(
        table=table,
        filename=path.name,
        relative_path=f"table={table}/{path.name}",
        sha256=sha256_file(path),
        byte_count=path.stat().st_size,
        row_count=row_count,
        source_filename=TABLES[table].filename,
        source_sha256=source_sha256,
        source_row_count=source_row_count,
    )


def _finalize_batch(temp_dir: Path, build_dir: Path, manifest: BatchManifest) -> Path:
    final_dir = build_dir / manifest.batch_id
    manifest_path = temp_dir / "manifest.json"
    manifest_path.write_bytes(manifest.to_bytes())
    if final_dir.exists():
        existing = final_dir / "manifest.json"
        if not existing.is_file() or existing.read_bytes() != manifest.to_bytes():
            raise ObjectConflictError(f"Existing local batch conflicts: {final_dir}")
        return final_dir
    temp_dir.replace(final_dir)
    return final_dir


def build_batches(
    data_dir: Path,
    build_dir: Path,
    *,
    source_version: str = DEFAULT_SOURCE_VERSION,
    reference_ingestion_date: str = "2021-10-01",
) -> List[Path]:
    missing = [contract.filename for contract in TABLES.values() if not (data_dir / contract.filename).is_file()]
    if missing:
        raise FileNotFoundError("Missing dataset files: " + ", ".join(missing))
    build_dir.mkdir(parents=True, exist_ok=True)
    source_metadata = _source_metadata(data_dir)

    order_month: Dict[str, str] = {}
    customer_month: Dict[str, str] = {}
    orders_path = data_dir / TABLES["orders"].filename
    with orders_path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            month = row["order_purchase_timestamp"][:7]
            order_month[row["order_id"]] = month
            customer_month[row["customer_id"]] = month

    completed: List[Path] = []
    for month in sorted(set(order_month.values())):
        with tempfile.TemporaryDirectory(prefix=f"olist-{month}-", dir=build_dir) as temporary:
            temp_dir = Path(temporary)
            files: List[ManifestFile] = []
            predicates = {
                "orders": lambda row, value=month: order_month[row["order_id"]] == value,
                "customers": lambda row, value=month: customer_month[row["customer_id"]] == value,
                "order_items": lambda row, value=month: order_month[row["order_id"]] == value,
                "order_payments": lambda row, value=month: order_month[row["order_id"]] == value,
                "order_reviews": lambda row, value=month: order_month[row["order_id"]] == value,
            }
            for table in TRANSACTION_TABLES:
                source_path = data_dir / TABLES[table].filename
                output_path = temp_dir / f"table={table}" / source_path.name
                row_count = _write_filtered_csv(source_path, output_path, predicates[table])
                source_sha, source_rows = source_metadata[table]
                files.append(
                    _manifest_file(
                        table=table,
                        path=output_path,
                        row_count=row_count,
                        source_sha256=source_sha,
                        source_row_count=source_rows,
                    )
                )
            window_start, window_end, ingestion_date = _month_bounds(month)
            manifest = BatchManifest.create(
                source=SOURCE,
                source_version=source_version,
                contract_version=CONTRACT_VERSION,
                batch_kind="transaction_month",
                logical_ingestion_date=ingestion_date,
                logical_ingestion_timestamp_utc=window_end,
                window_start_utc=window_start,
                window_end_utc=window_end,
                files=files,
            )
            completed.append(_finalize_batch(temp_dir, build_dir, manifest))
            _log("batch_built", batch_id=manifest.batch_id, batch_kind=manifest.batch_kind, month=month)

    with tempfile.TemporaryDirectory(prefix="olist-reference-", dir=build_dir) as temporary:
        temp_dir = Path(temporary)
        files = []
        for table in REFERENCE_TABLES:
            source_path = data_dir / TABLES[table].filename
            output_path = temp_dir / f"table={table}" / source_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, output_path)
            source_sha, source_rows = source_metadata[table]
            files.append(
                _manifest_file(
                    table=table,
                    path=output_path,
                    row_count=source_rows,
                    source_sha256=source_sha,
                    source_row_count=source_rows,
                )
            )
        manifest = BatchManifest.create(
            source=SOURCE,
            source_version=source_version,
            contract_version=CONTRACT_VERSION,
            batch_kind="reference_snapshot",
            logical_ingestion_date=reference_ingestion_date,
            logical_ingestion_timestamp_utc=reference_ingestion_date + "T00:00:00Z",
            window_start_utc=None,
            window_end_utc=None,
            files=files,
        )
        completed.append(_finalize_batch(temp_dir, build_dir, manifest))
        _log("batch_built", batch_id=manifest.batch_id, batch_kind=manifest.batch_kind)

    return sorted(completed)


def load_manifest(batch_dir: Path) -> BatchManifest:
    payload = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    files = tuple(
        ManifestFile(
            table=item["table"],
            filename=item["filename"],
            relative_path=item["relative_path"],
            sha256=item["sha256"],
            byte_count=item["byte_count"],
            row_count=item["row_count"],
            source_filename=item["source_filename"],
            source_sha256=item["source_sha256"],
            source_row_count=item["source_row_count"],
        )
        for item in payload["files"]
    )
    manifest = BatchManifest.create(
        source=payload["source"],
        source_version=payload["source_version"],
        contract_version=payload["contract_version"],
        batch_kind=payload["batch_kind"],
        logical_ingestion_date=payload["logical_ingestion_date"],
        logical_ingestion_timestamp_utc=payload["logical_ingestion_timestamp_utc"],
        window_start_utc=payload["window_start_utc"],
        window_end_utc=payload["window_end_utc"],
        files=files,
    )
    if manifest.batch_id != payload["batch_id"]:
        raise ValueError(f"Manifest batch ID does not match content: {batch_dir}")
    return manifest


@dataclass(frozen=True)
class UploadSummary:
    batch_id: str
    uploaded: int
    skipped: int
    object_count: int


@dataclass(frozen=True)
class BatchValidationSummary:
    batch_count: int
    file_count: int
    object_count: int
    row_count: int


def validate_built_batches(batch_dirs: Sequence[Path]) -> BatchValidationSummary:
    batch_ids: Set[str] = set()
    table_rows: Dict[str, int] = {name: 0 for name in TABLES}
    source_rows: Dict[str, int] = {}
    file_count = 0
    for batch_dir in batch_dirs:
        manifest = load_manifest(batch_dir)
        if manifest.batch_id in batch_ids:
            raise ValueError(f"Duplicate batch ID: {manifest.batch_id}")
        batch_ids.add(manifest.batch_id)
        for item in manifest.files:
            path = batch_dir / item.relative_path
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.stat().st_size != item.byte_count or sha256_file(path) != item.sha256:
                raise ValueError(f"Batch artifact does not match manifest: {path}")
            if item.table in source_rows and source_rows[item.table] != item.source_row_count:
                raise ValueError(f"Inconsistent source row count for {item.table}")
            source_rows[item.table] = item.source_row_count
            table_rows[item.table] += item.row_count
            file_count += 1
    if set(source_rows) != set(TABLES):
        raise ValueError("Built batches do not contain all contracted source tables")
    mismatches = {
        table: {"batched": table_rows[table], "source": source_rows[table]}
        for table in TABLES
        if table_rows[table] != source_rows[table]
    }
    if mismatches:
        raise ValueError(f"Batched row totals do not reconcile to source: {mismatches}")
    return BatchValidationSummary(
        batch_count=len(batch_ids),
        file_count=file_count,
        object_count=file_count + len(batch_ids),
        row_count=sum(table_rows.values()),
    )


def _object_key(prefix: str, manifest: BatchManifest, relative_path: str) -> str:
    base = (
        f"{prefix.strip('/')}/source={manifest.source}/"
        f"ingestion_date={manifest.logical_ingestion_date}/batch_id={manifest.batch_id}"
    ).strip("/")
    return f"{base}/{relative_path}"


def _matches(
    store: ObjectStore,
    key: str,
    sha256: str,
    byte_count: int,
    *,
    retry_attempts: int,
) -> bool:
    try:
        remote = with_retry(lambda: store.head(key), attempts=retry_attempts)
    except ObjectNotFoundError:
        return False
    remote_sha = remote.metadata.get("sha256")
    if remote_sha != sha256 or remote.byte_count != byte_count:
        raise ObjectConflictError(f"Immutable object conflict at {key}")
    return True


def upload_batch(
    batch_dir: Path,
    store: ObjectStore,
    *,
    prefix: str = "olist/raw",
    retry_attempts: int = 4,
) -> UploadSummary:
    manifest = load_manifest(batch_dir)
    uploaded = 0
    skipped = 0
    manifest_key = _object_key(prefix, manifest, "manifest.json")
    manifest_bytes = manifest.to_bytes()

    if _matches(
        store,
        manifest_key,
        manifest.sha256,
        len(manifest_bytes),
        retry_attempts=retry_attempts,
    ):
        for item in manifest.files:
            key = _object_key(prefix, manifest, item.relative_path)
            if not _matches(
                store, key, item.sha256, item.byte_count, retry_attempts=retry_attempts
            ):
                raise RuntimeError(f"Committed batch is missing object: {key}")
        _log("batch_already_committed", batch_id=manifest.batch_id, manifest_key=manifest_key)
        return UploadSummary(manifest.batch_id, uploaded=0, skipped=len(manifest.files) + 1, object_count=len(manifest.files) + 1)

    for item in manifest.files:
        source_path = batch_dir / item.relative_path
        if sha256_file(source_path) != item.sha256 or source_path.stat().st_size != item.byte_count:
            raise ValueError(f"Local artifact no longer matches manifest: {source_path}")
        key = _object_key(prefix, manifest, item.relative_path)
        if _matches(
            store, key, item.sha256, item.byte_count, retry_attempts=retry_attempts
        ):
            skipped += 1
            continue
        metadata = {
            "batch-id": manifest.batch_id,
            "sha256": item.sha256,
            "source": manifest.source,
            "source-table": item.table,
            "source-version": manifest.source_version,
        }
        with_retry(
            lambda source_path=source_path, key=key, metadata=metadata: store.upload_file(
                source_path, key, metadata
            ),
            attempts=retry_attempts,
        )
        if not _matches(
            store, key, item.sha256, item.byte_count, retry_attempts=retry_attempts
        ):
            raise RuntimeError(f"Upload validation failed: {key}")
        uploaded += 1

    manifest_metadata = {
        "batch-id": manifest.batch_id,
        "sha256": manifest.sha256,
        "source": manifest.source,
        "source-version": manifest.source_version,
    }
    with_retry(
        lambda: store.put_bytes(manifest_bytes, manifest_key, manifest_metadata),
        attempts=retry_attempts,
    )
    if not _matches(
        store,
        manifest_key,
        manifest.sha256,
        len(manifest_bytes),
        retry_attempts=retry_attempts,
    ):
        raise RuntimeError(f"Manifest upload validation failed: {manifest_key}")
    uploaded += 1
    _log("batch_committed", batch_id=manifest.batch_id, uploaded=uploaded, skipped=skipped)
    return UploadSummary(
        manifest.batch_id,
        uploaded=uploaded,
        skipped=skipped,
        object_count=len(manifest.files) + 1,
    )


def upload_batches(
    batch_dirs: Sequence[Path],
    store: ObjectStore,
    *,
    prefix: str = "olist/raw",
    retry_attempts: int = 4,
) -> List[UploadSummary]:
    return [
        upload_batch(path, store, prefix=prefix, retry_attempts=retry_attempts)
        for path in batch_dirs
    ]


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--build-dir", type=Path, default=Path("data/processed/ingestion_batches"))
    parser.add_argument("--source-version", default=os.getenv("OLIST_SOURCE_VERSION", DEFAULT_SOURCE_VERSION))
    parser.add_argument("--prefix", default=os.getenv("S3_RAW_PREFIX", "olist/raw"))
    parser.add_argument("--backend", choices=("local", "s3"), default="local")
    parser.add_argument("--local-store", type=Path, default=Path("data/processed/mock_s3"))
    parser.add_argument("--bucket")
    parser.add_argument("--region")
    parser.add_argument("--profile")
    parser.add_argument("--retry-attempts", type=int, default=4)
    args = parser.parse_args(argv)
    _configure_logging()

    try:
        batches = build_batches(args.data_dir, args.build_dir, source_version=args.source_version)
        validation = validate_built_batches(batches)
        _log("batches_validated", **validation.__dict__)
        if args.backend == "s3":
            store: ObjectStore = S3ObjectStore(
                args.bucket or os.getenv("S3_BUCKET", ""),
                region=args.region or os.getenv("AWS_REGION"),
                profile=args.profile or os.getenv("AWS_PROFILE") or None,
            )
        else:
            store = LocalObjectStore(args.local_store)
        summaries = upload_batches(
            batches, store, prefix=args.prefix, retry_attempts=args.retry_attempts
        )
    except Exception:
        LOGGER.exception("Ingestion failed")
        return 1

    print(
        json.dumps(
            {
                "batches": len(summaries),
                "objects": sum(item.object_count for item in summaries),
                "records": validation.row_count,
                "skipped": sum(item.skipped for item in summaries),
                "uploaded": sum(item.uploaded for item in summaries),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
