"""Safe SQL rendering for Snowflake infrastructure and raw COPY commands."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

from .dataset import TABLES
from .manifest import BatchManifest, ManifestFile


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
SAFE_STAGE_PATH = re.compile(r"^[A-Za-z0-9_./=\-]+$")
TEMPLATE_TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def quote_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe Snowflake identifier: {value!r}")
    return f'"{value.upper()}"'


def quote_fqn(*parts: str) -> str:
    return ".".join(quote_identifier(part) for part in parts)


def quote_literal(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Snowflake string literals cannot contain NUL")
    return "'" + value.replace("'", "''") + "'"


def validate_s3_url(value: str) -> str:
    if not re.fullmatch(r"s3://[A-Za-z0-9][A-Za-z0-9.\-]*(?:/[A-Za-z0-9_./=\-]*)?/?", value):
        raise ValueError(f"Unsafe or invalid S3 URL: {value!r}")
    return value.rstrip("/") + "/"


@dataclass(frozen=True)
class SnowflakeNames:
    database: str = "OLIST_ANALYTICS"
    raw_schema: str = "RAW"
    staging_schema: str = "STAGING"
    intermediate_schema: str = "INTERMEDIATE"
    marts_schema: str = "MARTS"
    audit_schema: str = "AUDIT"
    file_format: str = "OLIST_CSV_FORMAT"
    stage: str = "OLIST_RAW_STAGE"

    def validate(self) -> None:
        for value in self.__dict__.values():
            quote_identifier(value)

    def table(self, schema: str, table: str) -> str:
        return quote_fqn(self.database, schema, table)

    @property
    def stage_fqn(self) -> str:
        return quote_fqn(self.database, self.raw_schema, self.stage)

    @property
    def file_format_fqn(self) -> str:
        return quote_fqn(self.database, self.raw_schema, self.file_format)


def infrastructure_context(
    names: SnowflakeNames,
    *,
    s3_url: str,
    storage_integration: str,
) -> Dict[str, str]:
    names.validate()
    file_format_fqn = f"{names.database.upper()}.{names.raw_schema.upper()}.{names.file_format.upper()}"
    return {
        "DATABASE": quote_identifier(names.database),
        "RAW_SCHEMA": quote_identifier(names.raw_schema),
        "STAGING_SCHEMA": quote_identifier(names.staging_schema),
        "INTERMEDIATE_SCHEMA": quote_identifier(names.intermediate_schema),
        "MARTS_SCHEMA": quote_identifier(names.marts_schema),
        "AUDIT_SCHEMA": quote_identifier(names.audit_schema),
        "FILE_FORMAT": quote_identifier(names.file_format),
        "STAGE": quote_identifier(names.stage),
        "S3_URL": quote_literal(validate_s3_url(s3_url)),
        "STORAGE_INTEGRATION": quote_identifier(storage_integration),
        "FILE_FORMAT_FQN_LITERAL": quote_literal(file_format_fqn),
    }


def render_template(template: str, context: Mapping[str, str]) -> str:
    tokens = set(TEMPLATE_TOKEN.findall(template))
    missing = sorted(tokens - set(context))
    if missing:
        raise ValueError(f"Missing SQL template values: {', '.join(missing)}")
    rendered = TEMPLATE_TOKEN.sub(lambda match: context[match.group(1)], template)
    unresolved = TEMPLATE_TOKEN.findall(rendered)
    if unresolved:
        raise ValueError(f"Unresolved SQL template values: {unresolved}")
    return rendered


def render_infrastructure(
    sql_dir: Path,
    names: SnowflakeNames,
    *,
    s3_url: str,
    storage_integration: str,
) -> List[Tuple[str, str]]:
    context = infrastructure_context(
        names, s3_url=s3_url, storage_integration=storage_integration
    )
    files = sorted(sql_dir.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise FileNotFoundError(f"No Snowflake SQL files found in {sql_dir}")
    return [
        (path.name, render_template(path.read_text(encoding="utf-8"), context))
        for path in files
    ]


def stage_relative_path(manifest: BatchManifest, item: ManifestFile) -> str:
    value = (
        f"source={manifest.source}/ingestion_date={manifest.logical_ingestion_date}/"
        f"batch_id={manifest.batch_id}/{item.relative_path}"
    )
    if not SAFE_STAGE_PATH.fullmatch(value):
        raise ValueError(f"Unsafe stage path: {value!r}")
    return value


def _stage_directory_and_file(manifest: BatchManifest, item: ManifestFile) -> Tuple[str, str]:
    relative = stage_relative_path(manifest, item)
    directory, filename = relative.rsplit("/", 1)
    return directory, filename


def build_validation_sql(
    names: SnowflakeNames,
    manifest: BatchManifest,
    item: ManifestFile,
    validation_table: str,
) -> str:
    directory, filename = _stage_directory_and_file(manifest, item)
    target = quote_identifier(validation_table)
    return f"""COPY INTO {target}
FROM @{names.stage_fqn}/{directory}/
FILES = ({quote_literal(filename)})
FILE_FORMAT = (FORMAT_NAME = {quote_literal(names.file_format_fqn.replace(chr(34), ''))})
VALIDATION_MODE = 'RETURN_ALL_ERRORS'"""


def build_copy_sql(
    names: SnowflakeNames,
    manifest: BatchManifest,
    item: ManifestFile,
    run_id: str,
) -> str:
    contract = TABLES[item.table]
    columns = [quote_identifier(column) for column in contract.required_columns]
    metadata_columns = [
        '"_BATCH_ID"',
        '"_SOURCE_FILE"',
        '"_FILE_SHA256"',
        '"_SOURCE_VERSION"',
        '"_LOGICAL_INGESTION_DATE"',
        '"_SOURCE_ROW_NUMBER"',
        '"_LOAD_RUN_ID"',
    ]
    selections = [f"${index}" for index in range(1, len(columns) + 1)]
    selections.extend(
        [
            quote_literal(manifest.batch_id),
            "METADATA$FILENAME",
            quote_literal(item.sha256),
            quote_literal(manifest.source_version),
            f"TO_DATE({quote_literal(manifest.logical_ingestion_date)})",
            "METADATA$FILE_ROW_NUMBER",
            quote_literal(run_id),
        ]
    )
    directory, filename = _stage_directory_and_file(manifest, item)
    target = names.table(names.raw_schema, item.table)
    return f"""COPY INTO {target} ({', '.join(columns + metadata_columns)})
FROM (
    SELECT {', '.join(selections)}
    FROM @{names.stage_fqn}/{directory}/
)
FILES = ({quote_literal(filename)})
FILE_FORMAT = (FORMAT_NAME = {quote_literal(names.file_format_fqn.replace(chr(34), ''))})
ON_ERROR = 'ABORT_STATEMENT'
FORCE = FALSE"""


def validation_table_sql(table: str, validation_table: str) -> str:
    columns = TABLES[table].required_columns
    definitions = ", ".join(f"{quote_identifier(column)} VARCHAR" for column in columns)
    return f"CREATE OR REPLACE TEMPORARY TABLE {quote_identifier(validation_table)} ({definitions})"


def expected_raw_columns(table: str) -> Tuple[str, ...]:
    return TABLES[table].required_columns + (
        "_batch_id",
        "_source_file",
        "_file_sha256",
        "_source_version",
        "_logical_ingestion_date",
        "_source_row_number",
        "_load_run_id",
        "_loaded_at",
    )
