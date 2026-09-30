"""Snowflake RAW bootstrap, manifest-driven loading, audit, and reconciliation."""

import argparse
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

from .dataset import TABLES
from .ingestion import load_manifest
from .manifest import BatchManifest, ManifestFile
from .snowflake_sql import (
    SnowflakeNames,
    build_copy_sql,
    build_validation_sql,
    expected_raw_columns,
    quote_fqn,
    quote_identifier,
    render_infrastructure,
    stage_relative_path,
    validation_table_sql,
)


class WarehouseLoadError(RuntimeError):
    """Raised when validation, loading, or reconciliation fails."""


@dataclass(frozen=True)
class CopyResult:
    rows_loaded: int
    query_id: Optional[str] = None
    first_error: Optional[str] = None


@dataclass(frozen=True)
class CompletedBatch:
    expected_files: int
    loaded_files: int
    expected_rows: int
    loaded_rows: int


@dataclass(frozen=True)
class WarehouseLoadSummary:
    run_id: str
    batches_loaded: int
    batches_skipped: int
    files_loaded: int
    rows_loaded: int


@dataclass(frozen=True)
class WarehousePlanSummary:
    infrastructure_files: int
    batches: int
    data_files: int
    expected_rows: int


class WarehouseBackend(Protocol):
    def start_run(self, run_id: str, batches: int, expected_rows: int) -> None:
        ...

    def completed_batch(self, batch_id: str) -> Optional[CompletedBatch]:
        ...

    def count_batch_rows(self, manifest: BatchManifest) -> int:
        ...

    def validate_file(
        self, run_id: str, manifest: BatchManifest, item: ManifestFile
    ) -> List[Mapping[str, object]]:
        ...

    def record_validation_errors(
        self,
        run_id: str,
        manifest: BatchManifest,
        item: ManifestFile,
        errors: Sequence[Mapping[str, object]],
    ) -> None:
        ...

    def begin_batch(self, run_id: str, manifest: BatchManifest) -> None:
        ...

    def copy_file(
        self, run_id: str, manifest: BatchManifest, item: ManifestFile
    ) -> CopyResult:
        ...

    def count_file_rows(self, manifest: BatchManifest, item: ManifestFile) -> int:
        ...

    def record_file_success(
        self,
        run_id: str,
        manifest: BatchManifest,
        item: ManifestFile,
        result: CopyResult,
    ) -> None:
        ...

    def complete_batch(self, run_id: str, manifest: BatchManifest) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def record_batch_failure(
        self, run_id: str, manifest: BatchManifest, message: str
    ) -> None:
        ...

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        batches_loaded: int,
        batches_skipped: int,
        rows_loaded: int,
        error_message: Optional[str],
    ) -> None:
        ...


class WarehouseLoader:
    def __init__(self, backend: WarehouseBackend) -> None:
        self.backend = backend

    def load(self, batch_dirs: Sequence[Path], run_id: Optional[str] = None) -> WarehouseLoadSummary:
        manifests = [load_manifest(path) for path in sorted(batch_dirs)]
        if not manifests:
            raise ValueError("No ingestion batches were provided")
        current_run = run_id or str(uuid.uuid4())
        expected_rows = sum(sum(item.row_count for item in manifest.files) for manifest in manifests)
        loaded_batches = skipped_batches = loaded_files = loaded_rows = 0
        self.backend.start_run(current_run, len(manifests), expected_rows)
        try:
            for manifest in manifests:
                expected_batch_rows = sum(item.row_count for item in manifest.files)
                completed = self.backend.completed_batch(manifest.batch_id)
                if completed is not None:
                    if completed != CompletedBatch(
                        expected_files=len(manifest.files),
                        loaded_files=len(manifest.files),
                        expected_rows=expected_batch_rows,
                        loaded_rows=expected_batch_rows,
                    ):
                        raise WarehouseLoadError(
                            f"Completed audit record does not reconcile for {manifest.batch_id}"
                        )
                    if self.backend.count_batch_rows(manifest) != expected_batch_rows:
                        raise WarehouseLoadError(
                            f"Warehouse rows do not reconcile for completed batch {manifest.batch_id}"
                        )
                    skipped_batches += 1
                    continue

                existing_rows = self.backend.count_batch_rows(manifest)
                if existing_rows:
                    raise WarehouseLoadError(
                        f"Uncommitted rows exist for batch {manifest.batch_id}: {existing_rows}"
                    )

                validation_errors: List[Tuple[ManifestFile, Sequence[Mapping[str, object]]]] = []
                for item in manifest.files:
                    errors = self.backend.validate_file(current_run, manifest, item)
                    if errors:
                        self.backend.record_validation_errors(
                            current_run, manifest, item, errors
                        )
                        validation_errors.append((item, errors))
                if validation_errors:
                    count = sum(len(errors) for _, errors in validation_errors)
                    message = f"Pre-load validation found {count} rejected records"
                    self.backend.record_batch_failure(current_run, manifest, message)
                    raise WarehouseLoadError(f"{manifest.batch_id}: {message}")

                self.backend.begin_batch(current_run, manifest)
                batch_files_loaded = 0
                batch_rows_loaded = 0
                try:
                    for item in manifest.files:
                        result = self.backend.copy_file(current_run, manifest, item)
                        actual_rows = self.backend.count_file_rows(manifest, item)
                        if result.rows_loaded != item.row_count or actual_rows != item.row_count:
                            raise WarehouseLoadError(
                                f"{manifest.batch_id}/{item.table}: expected {item.row_count}, "
                                f"copy reported {result.rows_loaded}, warehouse contains {actual_rows}"
                            )
                        self.backend.record_file_success(
                            current_run, manifest, item, result
                        )
                        batch_files_loaded += 1
                        batch_rows_loaded += actual_rows
                    self.backend.complete_batch(current_run, manifest)
                    self.backend.commit()
                    loaded_batches += 1
                    loaded_files += batch_files_loaded
                    loaded_rows += batch_rows_loaded
                except Exception as exc:
                    self.backend.rollback()
                    self.backend.record_batch_failure(current_run, manifest, str(exc))
                    raise
        except Exception as exc:
            self.backend.finish_run(
                current_run,
                status="FAILED",
                batches_loaded=loaded_batches,
                batches_skipped=skipped_batches,
                rows_loaded=loaded_rows,
                error_message=str(exc),
            )
            raise

        self.backend.finish_run(
            current_run,
            status="SUCCEEDED",
            batches_loaded=loaded_batches,
            batches_skipped=skipped_batches,
            rows_loaded=loaded_rows,
            error_message=None,
        )
        return WarehouseLoadSummary(
            run_id=current_run,
            batches_loaded=loaded_batches,
            batches_skipped=skipped_batches,
            files_loaded=loaded_files,
            rows_loaded=loaded_rows,
        )


@dataclass(frozen=True)
class SnowflakeSettings:
    account: str
    user: str
    role: str
    warehouse: str
    private_key_file: str
    private_key_file_pwd: Optional[str]
    storage_integration: str
    s3_bucket: str
    s3_raw_prefix: str
    names: SnowflakeNames

    @classmethod
    def from_env(cls) -> "SnowflakeSettings":
        required = (
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_ROLE",
            "SNOWFLAKE_WAREHOUSE",
            "SNOWFLAKE_PRIVATE_KEY_PATH",
            "SNOWFLAKE_STORAGE_INTEGRATION",
            "S3_BUCKET",
        )
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError("Missing required configuration: " + ", ".join(missing))
        names = SnowflakeNames(
            database=os.getenv("SNOWFLAKE_DATABASE", "OLIST_ANALYTICS"),
            raw_schema=os.getenv("SNOWFLAKE_RAW_SCHEMA", "RAW"),
            staging_schema=os.getenv("SNOWFLAKE_STAGING_SCHEMA", "STAGING"),
            intermediate_schema=os.getenv("SNOWFLAKE_INTERMEDIATE_SCHEMA", "INTERMEDIATE"),
            marts_schema=os.getenv("SNOWFLAKE_MARTS_SCHEMA", "MARTS"),
            audit_schema=os.getenv("SNOWFLAKE_AUDIT_SCHEMA", "AUDIT"),
            file_format=os.getenv("SNOWFLAKE_FILE_FORMAT", "OLIST_CSV_FORMAT"),
            stage=os.getenv("SNOWFLAKE_STAGE", "OLIST_RAW_STAGE"),
        )
        names.validate()
        return cls(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            role=os.environ["SNOWFLAKE_ROLE"],
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
            private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
            private_key_file_pwd=os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
            storage_integration=os.environ["SNOWFLAKE_STORAGE_INTEGRATION"],
            s3_bucket=os.environ["S3_BUCKET"],
            s3_raw_prefix=os.getenv("S3_RAW_PREFIX", "olist/raw").strip("/"),
            names=names,
        )

    @property
    def s3_url(self) -> str:
        return f"s3://{self.s3_bucket}/{self.s3_raw_prefix}/"


def connect_snowflake(settings: SnowflakeSettings, *, include_database: bool = True):
    key_path = Path(settings.private_key_file).expanduser()
    if not key_path.is_file():
        raise FileNotFoundError(f"Snowflake private key file not found: {key_path}")
    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError("Install the cloud dependency group: pip install -e '.[cloud]'") from exc
    parameters = {
        "account": settings.account,
        "user": settings.user,
        "authenticator": "SNOWFLAKE_JWT",
        "private_key_file": str(key_path),
        "role": settings.role,
        "warehouse": settings.warehouse,
        "autocommit": False,
        "application": "olist_elt_pipeline",
    }
    if settings.private_key_file_pwd:
        parameters["private_key_file_pwd"] = settings.private_key_file_pwd
    if include_database:
        parameters["database"] = settings.names.database
        parameters["schema"] = settings.names.raw_schema
    return snowflake.connector.connect(**parameters)


def execute_infrastructure(connection: object, settings: SnowflakeSettings, sql_dir: Path) -> None:
    for _, sql in render_infrastructure(
        sql_dir,
        settings.names,
        s3_url=settings.s3_url,
        storage_integration=settings.storage_integration,
    ):
        connection.execute_string(sql)
    connection.commit()


def validate_local_plan(sql_dir: Path, batch_dirs: Sequence[Path]) -> WarehousePlanSummary:
    names = SnowflakeNames()
    infrastructure = render_infrastructure(
        sql_dir,
        names,
        s3_url="s3://example-approved-bucket/olist/raw/",
        storage_integration="EXAMPLE_STORAGE_INTEGRATION",
    )
    manifests = [load_manifest(path) for path in sorted(batch_dirs)]
    data_files = expected_rows = 0
    for manifest in manifests:
        for item in manifest.files:
            build_validation_sql(names, manifest, item, "VALIDATE_SOURCE_FILE")
            build_copy_sql(names, manifest, item, "local-plan-validation")
            data_files += 1
            expected_rows += item.row_count
    return WarehousePlanSummary(
        infrastructure_files=len(infrastructure),
        batches=len(manifests),
        data_files=data_files,
        expected_rows=expected_rows,
    )


def validate_remote_warehouse(
    connection: object,
    names: SnowflakeNames,
    batch_dirs: Sequence[Path],
) -> Mapping[str, int]:
    manifests = [load_manifest(path) for path in sorted(batch_dirs)]
    expected_rows: Dict[str, int] = {table: 0 for table in TABLES}
    expected_files = 0
    for manifest in manifests:
        for item in manifest.files:
            expected_rows[item.table] += item.row_count
            expected_files += 1

    cursor = connection.cursor()
    expected_schemas = {
        names.raw_schema.upper(),
        names.staging_schema.upper(),
        names.intermediate_schema.upper(),
        names.marts_schema.upper(),
        names.audit_schema.upper(),
    }
    cursor.execute(
        f"SELECT schema_name FROM {quote_fqn(names.database, 'INFORMATION_SCHEMA', 'SCHEMATA')} "
        "WHERE schema_name IN (%s,%s,%s,%s,%s)",
        tuple(sorted(expected_schemas)),
    )
    actual_schemas = {str(row[0]).upper() for row in cursor.fetchall()}
    if actual_schemas != expected_schemas:
        raise WarehouseLoadError(
            f"Schema mismatch: expected {sorted(expected_schemas)}, found {sorted(actual_schemas)}"
        )

    cursor.execute(
        f"SELECT table_name,column_name FROM "
        f"{quote_fqn(names.database, 'INFORMATION_SCHEMA', 'COLUMNS')} WHERE table_schema=%s",
        (names.raw_schema.upper(),),
    )
    actual_columns: Dict[str, set] = {}
    for table_name, column_name in cursor.fetchall():
        actual_columns.setdefault(str(table_name).lower(), set()).add(str(column_name).lower())
    for table in TABLES:
        expected = set(expected_raw_columns(table))
        if actual_columns.get(table) != expected:
            raise WarehouseLoadError(f"RAW column contract mismatch for {table}")

    cursor.execute(
        f"SELECT table_name,row_count FROM "
        f"{names.table(names.audit_schema, 'RAW_TABLE_COUNTS')}"
    )
    actual_rows = {str(table): int(count) for table, count in cursor.fetchall()}
    if actual_rows != expected_rows:
        raise WarehouseLoadError(
            f"RAW row totals do not match manifests: expected={expected_rows}, actual={actual_rows}"
        )

    cursor.execute(
        f"SELECT COUNT(*) FROM {names.table(names.audit_schema, 'BATCH_RECONCILIATION')} "
        "WHERE status <> 'SUCCEEDED' OR row_difference <> 0 OR file_difference <> 0"
    )
    if int(cursor.fetchone()[0]):
        raise WarehouseLoadError("Batch reconciliation contains failures or count differences")
    cursor.execute(
        f"SELECT COUNT(*) FROM {names.table(names.audit_schema, 'BATCH_RECONCILIATION')} "
        "WHERE status='SUCCEEDED'"
    )
    reconciled_batches = int(cursor.fetchone()[0])
    if reconciled_batches != len(manifests):
        raise WarehouseLoadError(
            f"Expected {len(manifests)} reconciled batches, found {reconciled_batches}"
        )

    cursor.execute(
        f"SELECT COUNT(DISTINCT batch_id,table_name,artifact_sha256) "
        f"FROM {names.table(names.audit_schema, 'FILE_LOADS')} WHERE status='SUCCEEDED'"
    )
    loaded_files = int(cursor.fetchone()[0])
    if loaded_files != expected_files:
        raise WarehouseLoadError(f"Expected {expected_files} loaded files, found {loaded_files}")

    cursor.execute(
        f"SELECT COALESCE(SUM(violation_count),0) FROM "
        f"{names.table(names.audit_schema, 'RAW_KEY_VIOLATIONS')}"
    )
    key_violations = int(cursor.fetchone()[0])
    cursor.execute(
        f"SELECT COALESCE(SUM(orphan_rows),0) FROM "
        f"{names.table(names.audit_schema, 'RAW_RELATIONSHIP_VIOLATIONS')}"
    )
    relationship_violations = int(cursor.fetchone()[0])
    if key_violations or relationship_violations:
        raise WarehouseLoadError(
            f"Source contract violations: keys={key_violations}, relationships={relationship_violations}"
        )
    return {
        "schemas": len(actual_schemas),
        "raw_tables": len(actual_rows),
        "batches": reconciled_batches,
        "files": loaded_files,
        "rows": sum(actual_rows.values()),
        "key_violations": key_violations,
        "relationship_violations": relationship_violations,
    }


class SnowflakeBackend:
    """Snowflake connector implementation of the tested warehouse protocol."""

    def __init__(self, connection: object, names: SnowflakeNames) -> None:
        self.connection = connection
        self.names = names
        self.audit = names.table(names.audit_schema, "LOAD_RUNS")
        self.batch_audit = names.table(names.audit_schema, "BATCH_LOADS")
        self.file_audit = names.table(names.audit_schema, "FILE_LOADS")
        self.error_audit = names.table(names.audit_schema, "LOAD_ERRORS")

    def _execute(self, sql: str, params: Optional[Sequence[object]] = None):
        cursor = self.connection.cursor()
        cursor.execute(sql, params or ())
        return cursor

    def start_run(self, run_id: str, batches: int, expected_rows: int) -> None:
        self._execute(
            f"INSERT INTO {self.audit} (run_id,status,batches_expected,expected_rows) "
            "VALUES (%s,'RUNNING',%s,%s)",
            (run_id, batches, expected_rows),
        )
        self.connection.commit()

    def completed_batch(self, batch_id: str) -> Optional[CompletedBatch]:
        cursor = self._execute(
            f"SELECT expected_files,loaded_files,expected_rows,loaded_rows "
            f"FROM {self.batch_audit} WHERE batch_id=%s AND status='SUCCEEDED' "
            "ORDER BY completed_at DESC LIMIT 1",
            (batch_id,),
        )
        row = cursor.fetchone()
        return CompletedBatch(*(int(value) for value in row)) if row else None

    def count_batch_rows(self, manifest: BatchManifest) -> int:
        total = 0
        for item in manifest.files:
            total += self.count_file_rows(manifest, item)
        return total

    def _validation_table(self, run_id: str, table: str) -> str:
        return f"V_{run_id.replace('-', '')[:12]}_{table}".upper()

    def validate_file(
        self, run_id: str, manifest: BatchManifest, item: ManifestFile
    ) -> List[Mapping[str, object]]:
        table = self._validation_table(run_id, item.table)
        self._execute(validation_table_sql(item.table, table))
        cursor = self._execute(build_validation_sql(self.names, manifest, item, table))
        columns = [str(value[0]).lower() for value in (cursor.description or ())]
        query_id = getattr(cursor, "sfqid", None)
        return [dict(zip(columns, row), query_id=query_id) for row in cursor.fetchall()]

    def record_validation_errors(
        self,
        run_id: str,
        manifest: BatchManifest,
        item: ManifestFile,
        errors: Sequence[Mapping[str, object]],
    ) -> None:
        sql = (
            f"INSERT INTO {self.error_audit} "
            "(run_id,batch_id,table_name,source_file,query_id,error_code,error_message,"
            "error_line,error_character,rejected_record) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        cursor = self.connection.cursor()
        cursor.executemany(
            sql,
            [
                (
                    run_id,
                    manifest.batch_id,
                    item.table,
                    item.filename,
                    error.get("query_id"),
                    error.get("code"),
                    error.get("error"),
                    error.get("line"),
                    error.get("character"),
                    error.get("rejected_record"),
                )
                for error in errors
            ],
        )
        self.connection.commit()

    def begin_batch(self, run_id: str, manifest: BatchManifest) -> None:
        self._execute("BEGIN")
        expected_rows = sum(item.row_count for item in manifest.files)
        self._execute(
            f"INSERT INTO {self.batch_audit} "
            "(run_id,batch_id,batch_kind,source_version,logical_ingestion_date,status,"
            "expected_files,expected_rows) VALUES (%s,%s,%s,%s,%s,'RUNNING',%s,%s)",
            (
                run_id,
                manifest.batch_id,
                manifest.batch_kind,
                manifest.source_version,
                manifest.logical_ingestion_date,
                len(manifest.files),
                expected_rows,
            ),
        )

    def copy_file(
        self, run_id: str, manifest: BatchManifest, item: ManifestFile
    ) -> CopyResult:
        cursor = self._execute(build_copy_sql(self.names, manifest, item, run_id))
        columns = [str(value[0]).lower() for value in (cursor.description or ())]
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise WarehouseLoadError(f"COPY returned {len(rows)} results for {item.filename}")
        result = dict(zip(columns, rows[0]))
        return CopyResult(
            rows_loaded=int(result.get("rows_loaded", 0)),
            query_id=getattr(cursor, "sfqid", None),
            first_error=result.get("first_error"),
        )

    def count_file_rows(self, manifest: BatchManifest, item: ManifestFile) -> int:
        table = self.names.table(self.names.raw_schema, item.table)
        cursor = self._execute(
            f'SELECT COUNT(*) FROM {table} WHERE "_BATCH_ID"=%s AND "_FILE_SHA256"=%s',
            (manifest.batch_id, item.sha256),
        )
        return int(cursor.fetchone()[0])

    def record_file_success(
        self,
        run_id: str,
        manifest: BatchManifest,
        item: ManifestFile,
        result: CopyResult,
    ) -> None:
        self._execute(
            f"INSERT INTO {self.file_audit} "
            "(run_id,batch_id,table_name,stage_path,artifact_sha256,source_sha256,"
            "expected_rows,loaded_rows,status,copy_query_id,first_error) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'SUCCEEDED',%s,%s)",
            (
                run_id,
                manifest.batch_id,
                item.table,
                stage_relative_path(manifest, item),
                item.sha256,
                item.source_sha256,
                item.row_count,
                result.rows_loaded,
                result.query_id,
                result.first_error,
            ),
        )

    def complete_batch(self, run_id: str, manifest: BatchManifest) -> None:
        expected_rows = sum(item.row_count for item in manifest.files)
        self._execute(
            f"UPDATE {self.batch_audit} SET status='SUCCEEDED',loaded_files=%s,loaded_rows=%s,"
            "completed_at=CURRENT_TIMESTAMP() WHERE run_id=%s AND batch_id=%s",
            (len(manifest.files), expected_rows, run_id, manifest.batch_id),
        )

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def record_batch_failure(
        self, run_id: str, manifest: BatchManifest, message: str
    ) -> None:
        expected_rows = sum(item.row_count for item in manifest.files)
        self._execute(
            f"INSERT INTO {self.batch_audit} "
            "(run_id,batch_id,batch_kind,source_version,logical_ingestion_date,status,"
            "expected_files,expected_rows,error_message,completed_at) "
            "VALUES (%s,%s,%s,%s,%s,'FAILED',%s,%s,%s,CURRENT_TIMESTAMP())",
            (
                run_id,
                manifest.batch_id,
                manifest.batch_kind,
                manifest.source_version,
                manifest.logical_ingestion_date,
                len(manifest.files),
                expected_rows,
                message[:16000],
            ),
        )
        self.connection.commit()

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        batches_loaded: int,
        batches_skipped: int,
        rows_loaded: int,
        error_message: Optional[str],
    ) -> None:
        self._execute(
            f"UPDATE {self.audit} SET status=%s,batches_loaded=%s,batches_skipped=%s,"
            "loaded_rows=%s,error_message=%s,completed_at=CURRENT_TIMESTAMP() WHERE run_id=%s",
            (
                status,
                batches_loaded,
                batches_skipped,
                rows_loaded,
                error_message[:16000] if error_message else None,
                run_id,
            ),
        )
        self.connection.commit()


def _require_integration_opt_in() -> None:
    if os.getenv("OLIST_RUN_SNOWFLAKE_INTEGRATION") != "1":
        raise RuntimeError(
            "Real Snowflake execution requires explicit OLIST_RUN_SNOWFLAKE_INTEGRATION=1"
        )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("validate-local", "plan", "bootstrap", "load", "validate-remote")
    )
    parser.add_argument("--sql-dir", type=Path, default=Path("sql/snowflake"))
    parser.add_argument(
        "--batch-dir", type=Path, default=Path("data/processed/ingestion_batches")
    )
    args = parser.parse_args(argv)
    try:
        batch_dirs = [path.parent for path in sorted(args.batch_dir.glob("*/manifest.json"))]
        if args.action == "validate-local":
            summary = validate_local_plan(args.sql_dir, batch_dirs)
            print(json.dumps(summary.__dict__, sort_keys=True))
            return 0
        settings = SnowflakeSettings.from_env()
        rendered = render_infrastructure(
            args.sql_dir,
            settings.names,
            s3_url=settings.s3_url,
            storage_integration=settings.storage_integration,
        )
        if args.action == "plan":
            print(json.dumps({"files": [name for name, _ in rendered]}, sort_keys=True))
            return 0
        _require_integration_opt_in()
        if args.action == "bootstrap":
            connection = connect_snowflake(settings, include_database=False)
            try:
                execute_infrastructure(connection, settings, args.sql_dir)
            finally:
                connection.close()
            print(json.dumps({"bootstrap_files": len(rendered), "status": "succeeded"}))
            return 0
        connection = connect_snowflake(settings)
        try:
            if args.action == "validate-remote":
                result = validate_remote_warehouse(connection, settings.names, batch_dirs)
                print(json.dumps(result, sort_keys=True))
                return 0
            summary = WarehouseLoader(SnowflakeBackend(connection, settings.names)).load(batch_dirs)
        finally:
            connection.close()
        print(json.dumps(summary.__dict__, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc), "status": "failed"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
