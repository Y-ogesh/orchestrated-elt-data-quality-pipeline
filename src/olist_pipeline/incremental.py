"""Isolated, resumable historical replay using the existing loader and dbt project.

Only M6_<12 hexadecimal characters>_ relations are writable by this harness.
The original S3 stage is read-only. Production relations are fingerprinted.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

from .data_quality import collect_reconciliation, validate_reconciliation
from .dataset import TABLES
from .ingestion import load_manifest, validate_built_batches
from .snowflake_sql import build_copy_sql, quote_identifier
from .warehouse import (
    SnowflakeBackend,
    SnowflakeSettings,
    WarehouseLoader,
    WarehouseLoadError,
)
from .warehouse import connect_snowflake as connect

AUDIT_TABLES = ("LOAD_RUNS", "BATCH_LOADS", "FILE_LOADS", "LOAD_ERRORS")
FACTS = ("fct_orders", "fct_order_items", "fct_order_payments", "fct_order_reviews")


def replay_sequence(root: Path) -> list[Path]:
    """Reference snapshot first, then month order; independent of hash/path order."""
    paths = list(root.glob("*/manifest.json"))
    return sorted(
        [p.parent for p in paths],
        key=lambda p: (
            load_manifest(p).batch_kind != "reference_snapshot",
            load_manifest(p).window_start_utc or "",
            load_manifest(p).batch_id,
        ),
    )


def validate_prefix(prefix: str) -> str:
    if not re.fullmatch(r"M6_[A-F0-9]{12}_", prefix):
        raise ValueError("Expected an isolated M6_<12 uppercase hex characters>_ prefix")
    return prefix


class InterruptAfterFirstFile(SnowflakeBackend):
    def record_file_success(self, run_id, manifest, item, result):
        super().record_file_success(run_id, manifest, item, result)
        raise WarehouseLoadError(
            "Intentional isolated interruption after first COPY and audit insert"
        )


class Replay:
    def __init__(self, prefix: str, root: Path):
        self.prefix = validate_prefix(prefix)
        self.settings = SnowflakeSettings.from_env()
        self.production = self.settings.names
        self.names = replace(self.production, relation_prefix=prefix)
        self.connection = connect(self.settings)
        self.root = root / prefix
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.root / "evidence.json"
        self.evidence = (
            json.loads(self.checkpoint.read_text())
            if self.checkpoint.exists()
            else {"prefix": prefix, "status": "Partially implemented", "steps": [], "dbt": []}
        )
        self.created = self.evidence.setdefault("created_relations", [])
        self.models = {
            p.stem: (
                "STAGING"
                if p.stem.startswith("stg_")
                else "INTERMEDIATE"
                if p.stem.startswith("int_")
                else "MARTS"
            )
            for p in Path("dbt/models").rglob("*.sql")
        }

    def save(self):
        self.checkpoint.write_text(json.dumps(self.evidence, indent=2, default=str) + "\n")

    def query(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def scalar(self, sql, params=()):
        return self.query(sql, params)[0][0]

    def relation(self, schema, name, production=False):
        return (self.production if production else self.names).table(schema, name)

    def create(self, schema, name, sql, kind="TABLE"):
        relation = self.relation(schema, name)
        self.query(sql)
        if [kind, relation] not in self.created:
            self.created.append([kind, relation])
        self.save()

    def fingerprints(self):
        results = {}
        relations = [("RAW", t) for t in TABLES] + [
            (s, m) for m, s in self.models.items() if s == "MARTS"
        ]
        for schema, name in relations:
            relation = self.relation(schema, name, production=True)
            count, checksum = self.query(f"SELECT COUNT(*), HASH_AGG(*) FROM {relation}")[0]
            results[name] = {"rows": count, "hash": str(checksum)}
        return results

    def bootstrap(self):
        if self.evidence.get("bootstrapped"):
            return
        self.evidence["production_before"] = self.fingerprints()
        for schema, tables in [("RAW", TABLES), ("AUDIT", AUDIT_TABLES)]:
            for name in tables:
                self.create(
                    schema,
                    name,
                    f"CREATE TABLE {self.relation(schema, name)} "
                    f"LIKE {self.relation(schema, name, production=True)}",
                )
        name = "BATCH_RECONCILIATION"
        self.create(
            "AUDIT",
            name,
            f"CREATE VIEW {self.relation('AUDIT', name)} AS SELECT "
            "batch_id,source_version,logical_ingestion_date,status,expected_files,"
            "loaded_files,expected_rows,loaded_rows,"
            "expected_rows-loaded_rows AS row_difference,"
            "expected_files-loaded_files AS file_difference,completed_at "
            f"FROM {self.relation('AUDIT', 'BATCH_LOADS')} "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY batch_id "
            "ORDER BY started_at DESC,completed_at DESC)=1",
            kind="VIEW",
        )
        self.evidence["bootstrapped"] = True
        self.save()

    def dbt(self, label, command="build", extra=()):
        profiles = self.root / "profiles"
        profiles.mkdir(exist_ok=True)
        (profiles / "profiles.yml").write_text(Path("dbt/profiles.yml.example").read_text())
        tag = f"{self.prefix}{label}"
        env = dict(
            os.environ,
            OLIST_RELATION_PREFIX=self.prefix,
            DBT_QUERY_TAG=tag,
            DBT_PROFILES_DIR=str(profiles.resolve()),
        )
        target = self.root / f"target_{label}"
        commands = [command, "freshness"] if command == "source" else [command]
        args = [
            str(Path(sys.executable).with_name("dbt")),
            *commands,
            "--project-dir",
            "dbt",
            "--target",
            "prod",
            "--target-path",
            str(target.resolve()),
            *(extra if command != "source" else ()),
        ]
        artifact = target / ("sources.json" if command == "source" else "run_results.json")
        result = json.loads(artifact.read_text()) if artifact.exists() else {}
        recovered = (
            bool(result.get("results"))
            and all(r["status"] in ("success", "pass", "warn") for r in result["results"])
            and not any(d["label"] == label for d in self.evidence["dbt"])
        )
        if recovered:
            elapsed = round(result["elapsed_time"], 3)
            returncode = 0
        else:
            started = time.perf_counter()
            with (self.root / f"{label}.log").open("w") as log:
                process = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT)
            elapsed = round(time.perf_counter() - started, 3)
            returncode = process.returncode
            result = json.loads(artifact.read_text()) if artifact.exists() else {}
        counts = dict(Counter(r["status"] for r in result.get("results", [])))
        summary = {
            "label": label,
            "command": command,
            "seconds": elapsed,
            "exit_code": returncode,
            "recovered_completed_artifact": recovered,
            "outcomes": counts,
        }
        if command in ("build", "run"):
            responses = [
                r["adapter_response"]
                for r in result.get("results", [])
                if r["unique_id"].split(".")[-1] in FACTS
            ]
            summary["merge_dml"] = {
                key: sum(r.get("rows_" + key, 0) for r in responses)
                for key in ("inserted", "updated", "deleted")
            }
            summary["merge_dml"]["statements"] = len(responses)
            for model, schema in self.models.items():
                relation = self.relation(schema, model)
                entry = ["TABLE" if schema == "MARTS" else "VIEW", relation]
                if entry not in self.created:
                    self.created.append(entry)
        self.evidence["dbt"].append(summary)
        self.save()
        print(json.dumps({"dbt": summary}), flush=True)
        if returncode:
            raise RuntimeError(f"dbt {label} failed; inspect ignored log {self.root / label}")
        return summary

    def audit_state(self, manifest):
        batch = self.relation("AUDIT", "BATCH_LOADS")
        files = self.relation("AUDIT", "FILE_LOADS")
        return {
            "statuses": [
                r[0]
                for r in self.query(
                    f"SELECT status FROM {batch} WHERE batch_id=%s ORDER BY started_at",
                    (manifest.batch_id,),
                )
            ],
            "committed_files": self.scalar(
                f"SELECT COUNT(*) FROM {files} WHERE batch_id=%s", (manifest.batch_id,)
            ),
            "committed_rows": SnowflakeBackend(self.connection, self.names).count_batch_rows(
                manifest
            ),
        }

    def load(self, path, label, interrupt=False):
        manifest = load_manifest(path)
        backend = (InterruptAfterFirstFile if interrupt else SnowflakeBackend)(
            self.connection, self.names
        )
        start = time.perf_counter()
        try:
            result = WarehouseLoader(backend).load([path])
        except WarehouseLoadError:
            if not interrupt:
                raise
            state = self.audit_state(manifest)
            assert state["statuses"][-1] == "FAILED", state
            assert state["committed_rows"] == state["committed_files"] == 0, state
            row = {
                "label": label,
                "batch_id": manifest.batch_id,
                "failure_state": state,
                "seconds": round(time.perf_counter() - start, 3),
            }
            self.evidence["interruption"] = row
            self.save()
            print(json.dumps(row), flush=True)
            return
        expected = sum(f.row_count for f in manifest.files)
        row = {
            "label": label,
            "batch_id": manifest.batch_id,
            "window": manifest.window_start_utc,
            "files_processed": result.files_loaded,
            "files_skipped": len(manifest.files) if result.batches_skipped else 0,
            "source_rows": expected,
            "inserted": result.rows_loaded,
            "updated": 0,
            "skipped": expected if result.batches_skipped else 0,
            "rejected": 0,
            "seconds": round(time.perf_counter() - start, 3),
            "reconciliation_difference": backend.count_batch_rows(manifest) - expected,
        }
        assert row["reconciliation_difference"] == 0
        self.evidence["steps"].append(row)
        self.save()
        print(json.dumps(row), flush=True)
        return row

    def replay(self, batch_root):
        sequence = replay_sequence(batch_root)
        inventory = asdict(validate_built_batches(sequence))
        self.evidence["source_inventory"] = inventory
        # Defer one historical month until after its successor; arrivals are simulated.
        sequence[3], sequence[4] = sequence[4], sequence[3]
        completed = {s["label"] for s in self.evidence["steps"]}
        for index, path in enumerate(sequence):
            label = f"batch_{index:02d}"
            if label not in completed:
                if index == 2 and "interruption" not in self.evidence:
                    self.load(path, "interrupted_batch", interrupt=True)
                self.load(path, label)
            if index and not any(d["label"] == label for d in self.evidence["dbt"]):
                self.dbt(label)
        if "duplicate_batch" not in completed:
            self.load(sequence[-1], "duplicate_batch")
            self.dbt("duplicate_dbt")
        recovered = self.audit_state(load_manifest(sequence[2]))
        assert recovered["statuses"] == ["FAILED", "SUCCEEDED"], recovered
        self.evidence["recovery"] = recovered
        self.save()

    def business_columns(self, schema, name, production=False):
        identifier = ("" if production else self.prefix) + name.upper()
        rows = self.query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (schema, identifier),
        )
        return [r[0] for r in rows if not r[0].startswith(("_", "SOURCE_"))]

    def compare(self, left, right, columns):
        cols = ",".join(quote_identifier(c) for c in columns)
        # Group multiplicities as well as values, preserving non-unique geography/reviews.
        a = f"SELECT {cols},COUNT(*) AS multiplicity FROM {left} GROUP BY ALL"
        b = f"SELECT {cols},COUNT(*) AS multiplicity FROM {right} GROUP BY ALL"
        difference = self.scalar(
            f"SELECT (SELECT COUNT(*) FROM (({a}) MINUS ({b}))) + "
            f"(SELECT COUNT(*) FROM (({b}) MINUS ({a})))"
        )
        counts = self.query(f"SELECT (SELECT COUNT(*) FROM {left}),(SELECT COUNT(*) FROM {right})")[
            0
        ]
        assert difference == 0 and counts[0] == counts[1], (difference, counts)
        return {
            "incremental_rows": counts[0],
            "baseline_rows": counts[1],
            "row_difference": counts[0] - counts[1],
            "business_record_difference": difference,
        }

    def convergence(self):
        results = {}
        for table in TABLES:
            results["raw_" + table] = self.compare(
                self.relation("RAW", table),
                self.relation("RAW", table, production=True),
                list(TABLES[table].required_columns),
            )
        for model, schema in self.models.items():
            self.create(
                schema,
                "BASE_" + model,
                f"CREATE TABLE {self.relation(schema, 'BASE_' + model)} AS "
                f"SELECT * FROM {self.relation(schema, model)}",
            )
        full = self.dbt("full_refresh", extra=("--full-refresh",))
        for model, schema in self.models.items():
            results[model] = self.compare(
                self.relation(schema, "BASE_" + model),
                self.relation(schema, model),
                self.business_columns(schema, model),
            )
        self.evidence["convergence"] = results
        self.evidence["full_refresh_seconds"] = full["seconds"]
        self.save()

    def metrics(self):
        fact = self.relation("MARTS", "fct_orders")
        row = self.query(
            f"SELECT COUNT(*),SUM(item_merchandise_value),SUM(freight_value),"
            f"SUM(payment_total_value) FROM {fact}"
        )[0]
        return dict(zip(("orders", "merchandise", "freight", "payments"), row))

    def isolated_business_state(self):
        result = {}
        for model, schema in self.models.items():
            columns = ",".join(quote_identifier(c) for c in self.business_columns(schema, model))
            result[model] = list(
                self.query(
                    f"SELECT COUNT(*),HASH_AGG({columns}) FROM {self.relation(schema, model)}"
                )[0]
            )
        return result

    def scenarios(self):
        """Apply controlled corrections/late rows only to harness-owned RAW copies."""
        items = self.relation("RAW", "ORDER_ITEMS")
        backup = self.relation("RAW", "SCENARIO_ITEM")
        self.create(
            "RAW",
            "SCENARIO_ITEM",
            f"CREATE TABLE {backup} AS SELECT * "
            f"FROM {items} ORDER BY shipping_limit_date,order_id,order_item_id LIMIT 1",
        )
        match = "t.order_id=b.order_id AND t.order_item_id=b.order_item_id"
        before = self.metrics()
        changed = self.query(
            f"UPDATE {items} t SET price=TO_VARCHAR(TO_DECIMAL(b.price,18,2)+1),"
            f"_loaded_at=b._loaded_at FROM {backup} b WHERE {match}"
        )[0][0]
        self.connection.commit()
        assert changed == 1
        result = self.dbt("changed_record")
        assert result["merge_dml"]["updated"] == 2 and result["merge_dml"]["inserted"] == 0
        after = self.metrics()
        assert after["merchandise"] - before["merchandise"] == 1
        repeat = self.dbt("changed_rerun")
        assert repeat["merge_dml"]["inserted"] == repeat["merge_dml"]["updated"] == 0
        self.evidence["changed_record"] = {
            "source_rows_changed": changed,
            "ingestion_timestamp_advanced": False,
            "merchandise_delta": "1.00",
            "merge_dml": result["merge_dml"],
            "rerun_merge_dml": repeat["merge_dml"],
        }
        changed_state = self.isolated_business_state()
        self.dbt("changed_full_refresh", extra=("--full-refresh",))
        assert self.isolated_business_state() == changed_state
        self.evidence["changed_record"]["full_refresh_equivalent"] = True
        self.query(
            f"UPDATE {items} t SET price=b.price,_loaded_at=CURRENT_TIMESTAMP() "
            f"FROM {backup} b WHERE {match}"
        )
        self.connection.commit()
        self.dbt("restore_correction")

        # A new component on an old order arrives now, with its old business timestamp intact.
        columns = list(TABLES["order_items"].required_columns) + [
            "_batch_id",
            "_source_file",
            "_file_sha256",
            "_source_version",
            "_logical_ingestion_date",
            "_source_row_number",
            "_load_run_id",
            "_loaded_at",
        ]
        selections = [
            "'9999'"
            if c == "order_item_id"
            else "'12.34'"
            if c == "price"
            else "'1.23'"
            if c == "freight_value"
            else "CURRENT_TIMESTAMP()"
            if c == "_loaded_at"
            else c
            for c in columns
        ]
        self.query(
            f"INSERT INTO {items} ({','.join(columns)}) SELECT {','.join(selections)} FROM {backup}"
        )
        self.connection.commit()
        late = self.dbt("late_arrival")
        late_metrics = self.metrics()
        assert str(late_metrics["merchandise"] - before["merchandise"]) == "12.34"
        assert str(late_metrics["freight"] - before["freight"]) == "1.23"
        old_days = self.scalar(
            f"SELECT DATEDIFF(day,TRY_TO_TIMESTAMP_NTZ(shipping_limit_date),"
            f"_loaded_at) FROM {items} WHERE order_item_id='9999'"
        )
        self.evidence["late_arrival"] = {
            "rows_added": 1,
            "business_age_days": old_days,
            "merge_dml": late["merge_dml"],
            "merchandise_delta": "12.34",
            "freight_delta": "1.23",
        }
        late_state = self.isolated_business_state()
        late_repeat = self.dbt("late_rerun")
        assert late_repeat["merge_dml"]["inserted"] == late_repeat["merge_dml"]["updated"] == 0
        self.dbt("late_full_refresh", extra=("--full-refresh",))
        assert self.isolated_business_state() == late_state
        self.evidence["late_arrival"]["full_refresh_equivalent"] = True
        self.evidence["late_arrival"]["rerun_merge_dml"] = late_repeat["merge_dml"]
        self.dbt("late_freshness", "source", ("freshness",))
        self.query(
            f"DELETE FROM {items} t USING {backup} b "
            "WHERE t.order_id=b.order_id AND t.order_item_id='9999'"
        )
        # Deletions are outside the merge contract; explicitly undo only the test-owned late fact.
        facts = self.relation("MARTS", "fct_order_items")
        self.query(
            f"DELETE FROM {facts} t USING {backup} b "
            "WHERE t.order_id=b.order_id AND t.order_item_id=9999"
        )
        self.connection.commit()
        self.dbt("restore_late")
        assert self.metrics() == before

        # An unexpected repeated business key must fail within the existing RAW transaction.
        backend = SnowflakeBackend(self.connection, self.names)
        item_batch_id = self.scalar(f"SELECT _batch_id FROM {backup}")
        item_manifest = next(
            load_manifest(p) for p in self.sequence if load_manifest(p).batch_id == item_batch_id
        )
        backend.begin_batch(str(uuid.uuid4()), item_manifest)
        self.query(f"INSERT INTO {items} SELECT * FROM {backup}")
        try:
            backend.validate_batch_keys(item_manifest)
        except WarehouseLoadError:
            backend.rollback()
            self.evidence["duplicate_business_key"] = {"outcome": "rejected", "committed_rows": 0}
        else:
            backend.rollback()
            raise AssertionError("Duplicate business key was not rejected")
        self.evidence["metrics"] = {k: str(v) for k, v in self.metrics().items()}
        self.save()

    def finish(self):
        required = (
            "changed_record",
            "late_arrival",
            "duplicate_business_key",
            "interruption",
            "recovery",
            "convergence",
        )
        if any(key not in self.evidence for key in required):
            raise RuntimeError("All replay, scenario, and convergence phases must succeed first")
        # Real duplicate COPY, bypassing only the loader's earlier batch-level skip.
        manifest = load_manifest(self.last_batch)
        item = manifest.files[0]
        before = SnowflakeBackend(self.connection, self.names).count_file_rows(manifest, item)
        with self.connection.cursor() as cursor:
            cursor.execute(build_copy_sql(self.names, manifest, item, str(uuid.uuid4())))
            columns = [r[0].lower() for r in cursor.description]
            rows = [dict(zip(columns, r)) for r in cursor.fetchall()]
        inserted = sum(int(r.get("rows_loaded", 0) or 0) for r in rows)
        self.connection.rollback()
        after_copy = SnowflakeBackend(self.connection, self.names).count_file_rows(manifest, item)
        if inserted or after_copy != before:
            raise RuntimeError("Duplicate file COPY changed isolated RAW rows")
        self.evidence["duplicate_file_copy"] = {
            "outcome": "skipped",
            "inserted": inserted,
            "row_difference": after_copy - before,
        }
        self.evidence["s3_duplicate_delivery"] = {
            "evidence": "reports/s3_validation.json",
            "validation": "prior Milestone 2 real AWS run",
            "uploaded": 0,
            "skipped": 155,
            "reexecuted_in_milestone_6": False,
        }
        after = self.fingerprints()
        assert after == self.evidence["production_before"], "Production fingerprint changed"
        reconciliation = collect_reconciliation(self.connection, self.production)
        validate_reconciliation(reconciliation)
        self.evidence["production_reconciliation"] = reconciliation
        self.evidence["production_unchanged"] = True
        self.evidence["status"] = "Completed and validated"
        self.save()

    def cleanup(self):
        # Only explicit objects created by this run; no wildcard DROP or schema/account DDL.
        for kind, relation in reversed(self.created):
            if f'."{self.prefix}' not in relation:
                raise ValueError("Cleanup target does not belong to this isolated run")
            self.query(f"DROP {kind} IF EXISTS {relation}")
        self.evidence["cleanup_objects"] = len(self.created)
        self.evidence["cleanup_complete"] = True
        remaining = self.scalar(
            "SELECT COUNT(*) FROM information_schema.tables WHERE STARTSWITH(table_name,%s)",
            (self.prefix,),
        )
        if remaining:
            raise RuntimeError(f"{remaining} isolated relations remain after cleanup")
        self.evidence["cleanup_remaining_relations"] = remaining
        self.save()
        if self.evidence.get("status") == "Completed and validated":
            report = {
                key: value
                for key, value in self.evidence.items()
                if key not in ("prefix", "created_relations", "production_before")
            }
            report["validation_schema_version"] = 1
            Path("reports/incremental_validation.json").write_text(
                json.dumps(report, indent=2, default=str) + "\n"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="M6_" + uuid.uuid4().hex[:12].upper() + "_")
    parser.add_argument("--batch-root", type=Path, default=Path("data/processed/ingestion_batches"))
    parser.add_argument("--artifact-root", type=Path, default=Path("data/processed/incremental"))
    parser.add_argument(
        "--phase",
        choices=("replay", "scenarios", "convergence", "finish", "cleanup"),
        default="replay",
    )
    args = parser.parse_args()
    if os.getenv("OLIST_RUN_SNOWFLAKE_INTEGRATION") != "1":
        raise RuntimeError("Explicit Snowflake integration opt-in required")
    runner = Replay(args.prefix, args.artifact_root)
    try:
        runner.sequence = replay_sequence(args.batch_root)
        runner.last_batch = runner.sequence[-1]
        if args.phase == "replay":
            runner.bootstrap()
            runner.replay(args.batch_root)
        elif args.phase == "scenarios":
            runner.scenarios()
        elif args.phase == "convergence":
            runner.convergence()
        elif args.phase == "finish":
            runner.dbt("final_tests", "test")
            runner.dbt("final_freshness", "source", ("freshness",))
            runner.finish()
        elif args.phase == "cleanup":
            runner.cleanup()
        print(json.dumps({"phase": args.phase, "evidence": str(runner.checkpoint)}))
    finally:
        runner.connection.close()


if __name__ == "__main__":
    main()
