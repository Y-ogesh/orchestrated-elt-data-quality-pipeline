"""Deterministic ingestion-manifest models."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


MANIFEST_SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


@dataclass(frozen=True)
class ManifestFile:
    table: str
    filename: str
    relative_path: str
    sha256: str
    byte_count: int
    row_count: int
    source_filename: str
    source_sha256: str
    source_row_count: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "filename": self.filename,
            "relative_path": self.relative_path,
            "row_count": self.row_count,
            "sha256": self.sha256,
            "source_filename": self.source_filename,
            "source_row_count": self.source_row_count,
            "source_sha256": self.source_sha256,
            "table": self.table,
        }


@dataclass(frozen=True)
class BatchManifest:
    source: str
    source_version: str
    contract_version: str
    batch_kind: str
    logical_ingestion_date: str
    logical_ingestion_timestamp_utc: str
    window_start_utc: Optional[str]
    window_end_utc: Optional[str]
    files: Tuple[ManifestFile, ...]
    batch_id: str

    @classmethod
    def create(
        cls,
        *,
        source: str,
        source_version: str,
        contract_version: str,
        batch_kind: str,
        logical_ingestion_date: str,
        logical_ingestion_timestamp_utc: str,
        window_start_utc: Optional[str],
        window_end_utc: Optional[str],
        files: Iterable[ManifestFile],
    ) -> "BatchManifest":
        sorted_files = tuple(sorted(files, key=lambda item: (item.table, item.filename)))
        identity = {
            "batch_kind": batch_kind,
            "contract_version": contract_version,
            "files": [item.to_dict() for item in sorted_files],
            "logical_ingestion_date": logical_ingestion_date,
            "logical_ingestion_timestamp_utc": logical_ingestion_timestamp_utc,
            "source": source,
            "source_version": source_version,
            "window_end_utc": window_end_utc,
            "window_start_utc": window_start_utc,
        }
        batch_id = hashlib.sha256(canonical_json(identity)).hexdigest()
        return cls(files=sorted_files, batch_id=batch_id, **{k: v for k, v in identity.items() if k != "files"})

    def to_dict(self) -> Dict[str, object]:
        return {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "batch_id": self.batch_id,
            "batch_kind": self.batch_kind,
            "contract_version": self.contract_version,
            "files": [item.to_dict() for item in self.files],
            "logical_ingestion_date": self.logical_ingestion_date,
            "logical_ingestion_timestamp_utc": self.logical_ingestion_timestamp_utc,
            "source": self.source,
            "source_version": self.source_version,
            "window_end_utc": self.window_end_utc,
            "window_start_utc": self.window_start_utc,
        }

    def to_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()
