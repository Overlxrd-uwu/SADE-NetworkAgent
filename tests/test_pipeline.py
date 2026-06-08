"""End-to-end pipeline test: env → session → agent → submit → eval.

Each ``test_step_*`` method runs in order against a real Kathara lab and the
mock agent. Steps share state through class attributes set by earlier steps.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/test_pipeline.py -v
"""

import csv
import json
import re
import unittest
from pathlib import Path

from typer.testing import CliRunner

from nika.cli.main import app
from nika.config import RESULTS_DIR
from nika.utils.session_store import SESSIONS_DIR, SessionStore

SCENARIO = "simple_bgp"
PROBLEM = "link_down"
class PipelineIntegrationTest(unittest.TestCase):
    """Run the full troubleshooting pipeline step by step via the NIKA CLI."""

    runner: CliRunner
    session_id: str | None = None
    session_dir: Path | None = None
    env_destroyed: bool = False

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = CliRunner()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.session_id and not cls.env_destroyed:
            cls.runner.invoke(app, ["env", "stop", "--session-id", cls.session_id])

    def _invoke_ok(self, args: list[str]) -> str:
        result = self.runner.invoke(app, args)
        self.assertEqual(result.exit_code, 0, result.output)
        return result.output

    def _load_json(self, filename: str) -> dict:
        assert self.session_dir is not None
        return json.loads((self.session_dir / filename).read_text(encoding="utf-8"))

    def _load_jsonl(self, filename: str) -> list[dict]:
        assert self.session_dir is not None
        return [
            json.loads(line)
            for line in (self.session_dir / filename).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_step_01_start_env(self) -> None:
        """Deploy a network scenario and capture the new session id."""
        list_output = self._invoke_ok(["env", "list"])
        self.assertIn(SCENARIO, list_output)

        run_output = self._invoke_ok(["env", "run", SCENARIO])
        match = re.search(r"session_id=(\S+)", run_output.strip())
        self.assertIsNotNone(match, f"session_id missing from env run output:\n{run_output}")
        type(self).session_id = match.group(1)

    def test_step_02_verify_session_running(self) -> None:
        """Confirm the session is active in env ps and session store."""
        self.assertIsNotNone(self.session_id)

        ps_output = self._invoke_ok(["env", "ps"])
        self.assertIn(self.session_id, ps_output)
        self.assertIn(f"scenario={SCENARIO}", ps_output)

        row = SessionStore().get_session(self.session_id)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["scenario_name"], SCENARIO)
        self.assertIsNotNone(row.get("lab_name"))

    def test_step_03_inject_failure(self) -> None:
        """Inject a fault and record ground truth for the session."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["failure", "inject", PROBLEM, "--session-id", self.session_id])

        ps_output = self._invoke_ok(["failure", "ps", "--session-id", self.session_id])
        self.assertIn(f"problem={PROBLEM}", ps_output)
        self.assertIn("status=injected", ps_output)

        row = SessionStore().get_session(self.session_id)
        self.assertIn(PROBLEM, row.get("problem_names", []))
        self.assertEqual(row["root_cause_name"], PROBLEM)

        type(self).session_dir = Path(row["session_dir"])
        self.assertTrue((self.session_dir / "ground_truth.json").exists())

        ground_truth = self._load_json("ground_truth.json")
        self.assertTrue(ground_truth["is_anomaly"])
        self.assertIn(PROBLEM, ground_truth["root_cause_name"])

    def test_step_04_run_mock_agent_diagnosis_and_submit(self) -> None:
        """Run the mock agent through diagnosis and final submission."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(
            [
                "agent",
                "run",
                "--agent",
                "mock",
                "--backend",
                "mock",
                "--model",
                "mock-v1",
                "--session-id",
                self.session_id,
            ]
        )

        self.assertTrue((self.session_dir / "messages.jsonl").exists())
        self.assertTrue((self.session_dir / "submission.json").exists())
        self.assertTrue((self.session_dir / "run.json").exists())

        messages = self._load_jsonl("messages.jsonl")
        agents = {entry["agent"] for entry in messages}
        self.assertIn("diagnosis_agent", agents)
        self.assertIn("submission_agent", agents)

        diagnosis_events = [e["event"] for e in messages if e["agent"] == "diagnosis_agent"]
        self.assertIn("tool_start", diagnosis_events)
        self.assertIn("llm_end", diagnosis_events)

        submission_tools = [
            e["tool"]["name"]
            for e in messages
            if e["agent"] == "submission_agent" and e["event"] == "tool_start"
        ]
        self.assertIn("list_avail_problems", submission_tools)
        self.assertIn("submit", submission_tools)

        submission = self._load_json("submission.json")
        for field in ("is_anomaly", "faulty_devices", "root_cause_name"):
            self.assertIn(field, submission)

        run = self._load_json("run.json")
        self.assertEqual(run["session_id"], self.session_id)
        self.assertEqual(run["agent_type"], "mock")

    def test_step_05_eval_metrics(self) -> None:
        """Compute rule-based scores from ground truth and submission."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["eval", "metrics", "--session-id", self.session_id])

        metrics_path = self.session_dir / "eval_metrics.json"
        self.assertTrue(metrics_path.exists())

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for field in (
            "detection_score",
            "localization_accuracy",
            "localization_f1",
            "rca_accuracy",
            "rca_f1",
            "tool_calls",
        ):
            self.assertIn(field, metrics)
        self.assertGreaterEqual(metrics["detection_score"], 0.0)
        self.assertGreater(metrics["tool_calls"], 0)

        row = SessionStore().get_session(self.session_id)
        self.assertIn("eval_metrics", row)

    def test_step_06_eval_publish_and_summary(self) -> None:
        """Finish the session, tear down the lab, and build a summary CSV offline."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["eval", "publish", "--session-id", self.session_id])
        type(self).env_destroyed = True

        run = self._load_json("run.json")
        self.assertEqual(run["status"], "finished")

        summary_output = self.session_dir / "session_summary.csv"
        self._invoke_ok(
            [
                "eval",
                "summary",
                "--session-id",
                self.session_id,
                "--output",
                str(summary_output),
            ]
        )

        self.assertTrue(summary_output.exists())
        with summary_output.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_id"], self.session_id)
        self.assertEqual(rows[0]["net_env"], SCENARIO)
        self.assertEqual(rows[0]["agent_type"], "mock")
        self.assertEqual(rows[0]["root_cause_name"], PROBLEM)

        ps_output = self.runner.invoke(app, ["env", "ps"])
        self.assertEqual(ps_output.exit_code, 0, ps_output.output)
        self.assertNotIn(self.session_id, ps_output.output)

        with self.assertRaises(FileNotFoundError):
            SessionStore().get_session(self.session_id)
        self.assertFalse((Path(SESSIONS_DIR) / f"{self.session_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
