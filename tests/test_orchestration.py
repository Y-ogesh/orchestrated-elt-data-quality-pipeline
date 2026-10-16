import importlib.metadata
import signal
import subprocess
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from olist_pipeline.orchestration import DAG_ID, TASKS, Workflow, require_gates, run_version
from olist_pipeline.snowflake_sql import SnowflakeNames


class PublicationTests(unittest.TestCase):
    def test_version_is_stable_and_identifier_safe(self):
        self.assertEqual(run_version("run/1"), run_version("run/1"))
        self.assertNotEqual(run_version("run/1"), run_version("run/2"))
        self.assertRegex(run_version("run/1"), r"^M7_[A-F0-9]{12}_$")

    def test_every_gate_must_succeed(self):
        good = {t: {"state": "success"} for t in TASKS[:6]}
        require_gates(good)
        for task in good:
            with self.subTest(task=task), self.assertRaises(RuntimeError):
                require_gates({**good, task: {"state": "failed"}})

    def test_failed_gate_prevents_publication_sql(self):
        workflow = object.__new__(Workflow)
        workflow.state = Mock(return_value={"state": "failed"})
        workflow.sql = Mock()
        with self.assertRaises(RuntimeError):
            workflow.publish_reporting()
        workflow.sql.assert_not_called()

    def test_publication_failure_rolls_back_pointer_and_copies(self):
        workflow = object.__new__(Workflow)
        workflow.names = SnowflakeNames()
        workflow.version = run_version("fixture")
        workflow.run_id = "fixture"
        workflow.connection = Mock()
        workflow.state = Mock(
            return_value={"state": "success", "result": {"reconciliation": {"monetary": {}}}}
        )
        workflow.publication_state = Mock(return_value=[("old_version",)])
        statements = []

        def execute(sql, params=()):
            statements.append(sql)
            if sql.startswith("INSERT INTO"):
                raise RuntimeError("isolated copy failure")
            return []

        workflow.sql = execute
        with self.assertRaises(RuntimeError):
            workflow.publish_reporting()
        workflow.connection.rollback.assert_called_once()
        workflow.connection.commit.assert_not_called()
        self.assertFalse(any(s.startswith("DELETE FROM") for s in statements))


def has_airflow():
    try:
        return bool(importlib.metadata.version("apache-airflow"))
    except importlib.metadata.PackageNotFoundError:
        return False


@unittest.skipUnless(has_airflow(), "requires pinned Airflow container")
class DagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from airflow.dag_processing.dagbag import DagBag

        cls.bag = DagBag(dag_folder="/opt/airflow/dags", known_pools={"olist_writer"})
        cls.dag = cls.bag.get_dag(DAG_ID)

    def test_import_and_inventory(self):
        self.assertEqual({}, self.bag.import_errors)
        self.assertIsNotNone(self.dag)
        self.assertEqual(set(TASKS), set(self.dag.task_ids))

    def test_dependencies_and_gates(self):
        for left, right in zip(TASKS[:-2], TASKS[1:-1]):
            self.assertIn(right, self.dag.get_task(left).downstream_task_ids)
        self.assertEqual("all_success", self.dag.get_task("publish_reporting").trigger_rule)
        audit = self.dag.get_task("record_pipeline_audit")
        self.assertEqual("all_done", audit.trigger_rule)
        self.assertEqual(set(TASKS[:-1]), audit.upstream_task_ids)

    def test_controls(self):
        self.assertEqual(1, self.dag.max_active_runs)
        self.assertEqual(1, self.dag.max_active_tasks)
        self.assertFalse(self.dag.catchup)
        self.assertEqual("0 6 * * 1", self.dag.schedule)
        self.assertEqual(timedelta(hours=2), self.dag.dagrun_timeout)
        for task in self.dag.tasks:
            self.assertEqual("olist_writer", task.pool)
            self.assertEqual(timedelta(minutes=30), task.execution_timeout)
            self.assertFalse(task.do_xcom_push)
            if task.task_id != "record_pipeline_audit":
                self.assertEqual(1, task.retries)
                self.assertEqual(timedelta(seconds=15), task.retry_delay)

    def test_boundary_timeout_terminates_owned_child_group(self):
        boundary = self.dag.get_task("prepare_source_batch").python_callable
        process = Mock(pid=12345)
        process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 1500), 0]
        process.poll.return_value = None
        context = {"ti": Mock(try_number=1), "dag_run": Mock(conf={}), "run_id": "fixture"}
        with patch("subprocess.Popen", return_value=process), patch("os.killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                boundary("prepare_source_batch", **context)
            kill.assert_called_once_with(12345, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
