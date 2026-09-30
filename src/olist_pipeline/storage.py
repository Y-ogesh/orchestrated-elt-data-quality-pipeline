"""Object-store adapters with integrity metadata and safe retries."""

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol, TypeVar


T = TypeVar("T")


class ObjectNotFoundError(Exception):
    """Raised when an object key does not exist."""


class ObjectConflictError(Exception):
    """Raised when an existing key has different immutable content."""


@dataclass(frozen=True)
class ObjectMetadata:
    byte_count: int
    metadata: Mapping[str, str]


class ObjectStore(Protocol):
    def head(self, key: str) -> ObjectMetadata:
        ...

    def upload_file(self, source: Path, key: str, metadata: Mapping[str, str]) -> None:
        ...

    def put_bytes(self, payload: bytes, key: str, metadata: Mapping[str, str]) -> None:
        ...


class LocalObjectStore:
    """Filesystem-backed S3 substitute used for local execution evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError(f"Object key escapes local store: {key}")
        return path

    def _metadata_path(self, key: str) -> Path:
        return self._path(key + ".olist-metadata.json")

    def head(self, key: str) -> ObjectMetadata:
        path = self._path(key)
        metadata_path = self._metadata_path(key)
        if not path.is_file() or not metadata_path.is_file():
            raise ObjectNotFoundError(key)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return ObjectMetadata(byte_count=path.stat().st_size, metadata=metadata)

    def upload_file(self, source: Path, key: str, metadata: Mapping[str, str]) -> None:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        self._write_metadata(key, metadata)

    def put_bytes(self, payload: bytes, key: str, metadata: Mapping[str, str]) -> None:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        self._write_metadata(key, metadata)

    def _write_metadata(self, key: str, metadata: Mapping[str, str]) -> None:
        path = self._metadata_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(metadata), sort_keys=True) + "\n", encoding="utf-8")


class S3ObjectStore:
    """Thin boto3 adapter. Credentials come only from the standard AWS provider chain."""

    def __init__(
        self,
        bucket: str,
        *,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        client: object = None,
    ) -> None:
        if not bucket:
            raise ValueError("An approved S3 bucket name is required")
        self.bucket = bucket
        if client is not None:
            self.client = client
            return
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install the cloud dependency group: pip install -e '.[cloud]'") from exc
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("s3")

    def head(self, key: str) -> ObjectMetadata:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError(key) from exc
            raise
        return ObjectMetadata(
            byte_count=int(response["ContentLength"]),
            metadata={str(k): str(v) for k, v in response.get("Metadata", {}).items()},
        )

    def upload_file(self, source: Path, key: str, metadata: Mapping[str, str]) -> None:
        self.client.upload_file(
            str(source),
            self.bucket,
            key,
            ExtraArgs={"Metadata": dict(metadata), "ServerSideEncryption": "AES256"},
        )

    def put_bytes(self, payload: bytes, key: str, metadata: Mapping[str, str]) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            Metadata=dict(metadata),
            ServerSideEncryption="AES256",
            ContentType="application/json",
        )


def is_retryable_exception(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    code = str(response.get("Error", {}).get("Code", ""))
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable"} or status in {
        429,
        500,
        502,
        503,
        504,
    }


def with_retry(
    operation: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt == attempts or not is_retryable_exception(exc):
                raise
            sleep(base_delay_seconds * (2 ** (attempt - 1)))
