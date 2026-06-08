"""Session persistence: file-based store and Session facade."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nika.utils.session import Session
from nika.utils.session_store import SessionStore


class _SessionStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sessions_dir = str(Path(self.temp_dir.name) / "sessions")
        self.store = SessionStore(sessions_dir=self.sessions_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()


class SessionStoreTest(_SessionStoreTestCase):
    def test_create_and_load_unique_running_session(self) -> None:
        """Load the only running session when exactly one exists."""
        self.store.create_session(
            {
                "session_id": "sid-1",
                "lab_name": "dc_clos_bgp__a",
                "scenario_name": "dc_clos_bgp",
                "scenario_topo_size": "s",
                "status": "running",
                "scenario_params": {"lab_name": "dc_clos_bgp__a", "topo_size": "s"},
            }
        )

        loaded = self.store.get_unique_running_session()
        self.assertEqual(loaded["session_id"], "sid-1")
        self.assertEqual(loaded["scenario_params"]["lab_name"], "dc_clos_bgp__a")

    def test_multiple_running_sessions_raise(self) -> None:
        """Raise when more than one session is running."""
        for suffix in ("a", "b"):
            self.store.create_session(
                {
                    "session_id": f"sid-{suffix}",
                    "lab_name": f"dc_clos_bgp__{suffix}",
                    "scenario_name": "dc_clos_bgp",
                    "status": "running",
                }
            )

        with self.assertRaises(ValueError):
            self.store.get_unique_running_session()

    def test_fields_roundtrip(self) -> None:
        """Persist and reload list and dict session fields."""
        self.store.create_session(
            {
                "session_id": "sid-json",
                "lab_name": "dc_clos_bgp__json",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
                "problem_names": ["link_down", "dhcp_service_down"],
                "eval_metrics": {"detection_score": 1.0},
            }
        )

        row = self.store.get_session("sid-json")
        self.assertEqual(row["problem_names"], ["link_down", "dhcp_service_down"])
        self.assertEqual(row["eval_metrics"]["detection_score"], 1.0)

    def test_failure_injection_create_list_and_mark_ended(self) -> None:
        """Track failure injections through create, update, and end."""
        self.store.create_session(
            {
                "session_id": "sid-failure",
                "lab_name": "dc_clos_bgp__failure",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
            }
        )
        failure_idx = self.store.create_failure_injection(
            {
                "session_id": "sid-failure",
                "problem_name": "link_down",
                "root_cause_category": "link_failure",
                "scenario_name": "dc_clos_bgp",
                "lab_name": "dc_clos_bgp__failure",
                "injection_params": {"faulty_devices": ["pc1"], "faulty_intf": "eth0"},
                "status": "pending",
                "start_time": 123.0,
            }
        )
        self.store.update_failure_injection("sid-failure", failure_idx, {"status": "injected"})

        rows = self.store.list_failure_injections(session_id="sid-failure")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["problem_name"], "link_down")
        self.assertEqual(rows[0]["status"], "injected")
        self.assertEqual(rows[0]["injection_params"]["faulty_intf"], "eth0")

        updated = self.store.mark_session_failures_ended("sid-failure", end_time=456.0)
        self.assertEqual(updated, 1)
        rows_after = self.store.list_failure_injections(session_id="sid-failure")
        self.assertEqual(rows_after[0]["status"], "ended")
        self.assertEqual(rows_after[0]["end_time"], 456.0)

    def test_delete_session_removes_json(self) -> None:
        """Delete the runtime session file once results are persisted."""
        self.store.create_session(
            {
                "session_id": "sid-delete",
                "lab_name": "dc_clos_bgp__delete",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
            }
        )
        path = Path(self.sessions_dir) / "sid-delete.json"
        self.assertTrue(path.exists())

        self.store.delete_session("sid-delete")
        self.assertFalse(path.exists())
        with self.assertRaises(FileNotFoundError):
            self.store.get_session("sid-delete")

    def test_count_failure_statuses(self) -> None:
        """Count failure injections grouped by status."""
        self.store.create_session(
            {
                "session_id": "sid-counts",
                "lab_name": "dc_clos_bgp__counts",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
            }
        )
        self.store.create_failure_injection(
            {
                "session_id": "sid-counts",
                "problem_name": "link_down",
                "status": "injected",
            }
        )
        self.store.create_failure_injection(
            {
                "session_id": "sid-counts",
                "problem_name": "host_crash",
                "status": "pending",
            }
        )
        counts = self.store.count_failure_statuses(session_id="sid-counts")
        self.assertEqual(counts["injected"], 1)
        self.assertEqual(counts["pending"], 1)


class SessionTest(_SessionStoreTestCase):
    def _new_session(self) -> Session:
        with patch("nika.utils.session.SessionStore", return_value=self.store):
            return Session()

    def test_load_running_session_by_id(self) -> None:
        """Load a running session by explicit session id."""
        self.store.create_session(
            {
                "session_id": "sid-1",
                "lab_name": "dc_clos_bgp__a",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
            }
        )
        session = self._new_session()
        session.load_running_session(session_id="sid-1")
        self.assertEqual(session.lab_name, "dc_clos_bgp__a")

    def test_load_running_rejects_non_running_status(self) -> None:
        """Reject loading a session that is not running."""
        self.store.create_session(
            {
                "session_id": "sid-finished",
                "lab_name": "dc_clos_bgp__done",
                "scenario_name": "dc_clos_bgp",
                "status": "finished",
            }
        )
        session = self._new_session()
        with self.assertRaises(ValueError):
            session.load_running_session(session_id="sid-finished")

    def test_update_session_sets_root_cause_and_session_dir(self) -> None:
        """Derive root cause and result directory from problem names."""
        self.store.create_session(
            {
                "session_id": "sid-rca",
                "lab_name": "dc_clos_bgp__rca",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
            }
        )
        session = self._new_session()
        session.load_running_session(session_id="sid-rca")
        with patch.object(session, "_write_run_json"):
            session.update_session("problem_names", ["link_down"])
        self.assertEqual(session.root_cause_name, "link_down")
        self.assertTrue(session.session_dir.endswith("/link_down/sid-rca"))

    def test_clear_session_writes_run_json_and_removes_runtime_file(self) -> None:
        """Finalize run.json in results and remove the runtime session document."""
        self.store.create_session(
            {
                "session_id": "sid-clear",
                "lab_name": "dc_clos_bgp__clear",
                "scenario_name": "dc_clos_bgp",
                "status": "running",
            }
        )
        session = self._new_session()
        session.load_running_session(session_id="sid-clear")
        with tempfile.TemporaryDirectory() as results_dir:
            session.session_dir = f"{results_dir}/link_down/sid-clear"
            session.clear_session()

            run_path = Path(session.session_dir) / "run.json"
            self.assertTrue(run_path.exists())
            run = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(run["status"], "finished")
            self.assertFalse((Path(self.sessions_dir) / "sid-clear.json").exists())
