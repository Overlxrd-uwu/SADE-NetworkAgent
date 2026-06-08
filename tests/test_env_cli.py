"""Integration tests for NIKA CLI with a real Kathara lab and mock agent.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/test_env_cli.py -v
"""

import json
import re
import unittest
from pathlib import Path

from typer.testing import CliRunner

from nika.cli.main import app
from nika.config import RESULTS_DIR

SCENARIO = "simple_bgp"
PROBLEM = "link_down"


class EnvCliIntegrationTest(unittest.TestCase):
    """Exercise main env, failure, exec, and agent CLI commands on a live session."""

    runner: CliRunner
    session_id: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = CliRunner()

        run_result = cls.runner.invoke(app, ["env", "run", SCENARIO])
        if run_result.exit_code != 0:
            raise RuntimeError(f"nika env run failed:\n{run_result.output}")
        match = re.search(r"session_id=(\S+)", run_result.output.strip())
        if match is None:
            raise RuntimeError(f"session_id missing from env run output:\n{run_result.output}")
        cls.session_id = match.group(1)

        inject_result = cls.runner.invoke(
            app,
            ["failure", "inject", PROBLEM, "--session-id", cls.session_id],
        )
        if inject_result.exit_code != 0:
            cls.runner.invoke(app, ["env", "stop", "--session-id", cls.session_id])
            raise RuntimeError(f"nika failure inject failed:\n{inject_result.output}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runner.invoke(app, ["env", "stop", "--session-id", cls.session_id])

    def test_env_list_includes_scenario(self) -> None:
        """List registered network scenarios."""
        result = self.runner.invoke(app, ["env", "list"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(SCENARIO, result.output)

    def test_env_ps_lists_running_session(self) -> None:
        """Show the running lab session."""
        result = self.runner.invoke(app, ["env", "ps"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(self.session_id, result.output)
        self.assertIn(f"scenario={SCENARIO}", result.output)
        self.assertIn("failures=", result.output)

    def test_failure_ps_lists_injected_fault(self) -> None:
        """List failure injections for the session."""
        result = self.runner.invoke(
            app,
            ["failure", "ps", "--session-id", self.session_id],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(f"problem={PROBLEM}", result.output)
        self.assertIn("status=injected", result.output)

    def test_failure_describe_prints_problem_help(self) -> None:
        """Describe parameters for an injectable problem."""
        result = self.runner.invoke(app, ["failure", "describe", PROBLEM])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(PROBLEM, result.output)

    def test_exec_runs_command_on_host(self) -> None:
        """Execute a command inside a lab host container."""
        result = self.runner.invoke(
            app,
            ["exec", "pc1", "hostname", "--session-id", self.session_id],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(result.output.strip())

    def test_agent_run_mock_writes_submission(self) -> None:
        """Run the mock agent and write troubleshooting artifacts."""
        result = self.runner.invoke(
            app,
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
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)

        session_dir = Path(RESULTS_DIR) / PROBLEM / self.session_id
        self.assertTrue((session_dir / "ground_truth.json").exists())
        self.assertTrue((session_dir / "submission.json").exists())
        self.assertTrue((session_dir / "run.json").exists())

        submission = json.loads((session_dir / "submission.json").read_text(encoding="utf-8"))
        for field in ("is_anomaly", "faulty_devices", "root_cause_name"):
            self.assertIn(field, submission)

        run = json.loads((session_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["session_id"], self.session_id)
        self.assertEqual(run["agent_type"], "mock")


if __name__ == "__main__":
    unittest.main()
