"""End-to-end pipeline integration test.

env → session → failure → MCP propagation → mock agent → close → eval.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/test_pipeline.py -v
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import unittest
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.utils.mcp_servers import MCPServerConfig
from nika.codex_cli.main import app
from nika.codex_cli.utils import env_id_from_lab
from nika.utils.session_store import SESSIONS_DIR, SessionStore
from tests.integration_base import OrderedPipelineTestCase

SCENARIO = "simple_bgp"
PROBLEM = "link_down"


def _tool_text_list(result: object) -> list[str]:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return [result]
    if not isinstance(result, list):
        return [str(result)]
    return [str(item["text"]) if isinstance(item, dict) and "text" in item else str(item) for item in result]


class PipelineIntegrationTest(OrderedPipelineTestCase):
    """Run the full troubleshooting pipeline step by step via the NIKA CLI."""

    def test_step_01_start_env(self) -> None:
        """Deploy a network scenario and capture the new session id."""
        list_output = self._invoke_ok(["env", "list"])
        self.assertIn(SCENARIO, list_output)

        run_output = self._invoke_ok(["env", "run", SCENARIO])
        match = re.search(r"session_id=(\S+)", run_output.strip())
        self.assertIsNotNone(match, f"session_id missing from env run output:\n{run_output}")
        type(self).session_id = match.group(1)

        self._assert_session_ready(self.session_id, SCENARIO)

    def test_step_02_verify_session_and_cli(self) -> None:
        """Confirm the session is active and basic CLI commands work on it."""
        self.assertIsNotNone(self.session_id)

        row = SessionStore().get_session(self.session_id)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["scenario_name"], SCENARIO)
        lab_name = row.get("lab_name")
        self.assertIsNotNone(lab_name)

        ps_output = self._invoke_ok(["env", "ps"])
        self.assertIn(env_id_from_lab(lab_name), ps_output)
        self.assertIn(SCENARIO, ps_output)
        self.assertIn("1 active", ps_output)

        session_ps_output = self._invoke_ok(["session", "ps"])
        self.assertIn(self.session_id, session_ps_output)

        inspect_output = self._invoke_ok(["session", "inspect"])
        self.assertIn(self.session_id, inspect_output)

        self._invoke_ok(["failure", "ps"])
        self._invoke_ok(["exec", "pc1", "hostname"])

        describe_output = self._invoke_ok(["failure", "describe", PROBLEM])
        self.assertIn(PROBLEM, describe_output)

        exec_output = self._invoke_ok(
            ["exec", "pc1", "hostname", "--session-id", self.session_id],
        )
        self.assertTrue(exec_output.strip())

    def test_step_03_inject_failure(self) -> None:
        """Inject a fault and record ground truth for the session."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(
            [
                "failure",
                "inject",
                PROBLEM,
                "--session-id",
                self.session_id,
                "--set",
                "host_name=pc1",
                "--set",
                "intf_name=eth0",
            ]
        )

        ps_output = self._invoke_ok(["failure", "ps", "--session-id", self.session_id])
        self.assertIn(f"problem={PROBLEM}", ps_output)
        self.assertIn("status=injected", ps_output)

        failures = SessionStore().list_failure_injections(session_id=self.session_id)
        self.assertEqual(len(failures), 1)
        injection_params = failures[0]["injection_params"]
        self.assertEqual(
            injection_params["requested_overrides"],
            {"host_name": "pc1", "intf_name": "eth0"},
        )
        resolved = injection_params["resolved_params"]
        self.assertEqual(resolved["host_name"], "pc1")
        self.assertEqual(resolved["intf_name"], "eth0")

        row = SessionStore().get_session(self.session_id)
        self.assertIn(PROBLEM, row.get("problem_names", []))
        self.assertEqual(row["root_cause_name"], PROBLEM)

        task_description = row.get("task_description", "")
        self.assertTrue(len(task_description) > 0, "task_description should be non-empty")

        session_dir_str = row.get("session_dir", "")
        self.assertIn(self.session_id, session_dir_str, "session_dir must contain session_id")

        type(self).session_dir = Path(session_dir_str)
        self.assertTrue((self.session_dir / "ground_truth.json").exists())

        ground_truth = self._load_json("ground_truth.json")
        self.assertTrue(ground_truth["is_anomaly"])
        self.assertIn(PROBLEM, ground_truth["root_cause_name"])

    def test_step_04_mcp_session_context(self) -> None:
        """mcp_session_context functions correctly read NIKA_SESSION_ID from env."""
        self.assertIsNotNone(self.session_id)

        row = SessionStore().get_session(self.session_id)
        expected_lab_name = row["lab_name"]
        expected_session_dir = row["session_dir"]

        prev = os.environ.get("NIKA_SESSION_ID")
        try:
            os.environ["NIKA_SESSION_ID"] = self.session_id

            from nika.service.mcp_server.mcp_session_context import (
                get_lab_name,
                get_session_dir,
                require_session_id,
            )

            resolved_id = require_session_id()
            self.assertEqual(resolved_id, self.session_id)

            resolved_lab = get_lab_name()
            self.assertEqual(resolved_lab, expected_lab_name)

            resolved_dir = get_session_dir()
            self.assertEqual(resolved_dir, expected_session_dir)

        finally:
            if prev is None:
                os.environ.pop("NIKA_SESSION_ID", None)
            else:
                os.environ["NIKA_SESSION_ID"] = prev

    def test_step_05_diagnosis_mcp_tools(self) -> None:
        """Diagnosis MCP tools spawned with NIKA_SESSION_ID execute against the correct lab."""
        self.assertIsNotNone(self.session_id)

        mcp_config = MCPServerConfig(session_id=self.session_id)
        server_env = mcp_config._server_env()
        self.assertEqual(
            server_env["NIKA_SESSION_ID"],
            self.session_id,
            "MCPServerConfig must set NIKA_SESSION_ID to the current session_id",
        )

        config = mcp_config.load_config(if_submit=False)
        diagnosis_config = {k: v for k, v in config.items() if k == "kathara_base_mcp_server"}

        async def _run() -> dict:
            client = MultiServerMCPClient(connections=diagnosis_config)
            tools = {t.name: t for t in await client.get_tools()}

            self.assertIn("get_reachability", tools, "get_reachability tool must be available")
            reach_result = await tools["get_reachability"].ainvoke({})
            reach_str = str(reach_result)
            self.assertTrue(len(reach_str) > 0, "get_reachability must return non-empty output")

            self.assertIn("get_host_net_config", tools, "get_host_net_config tool must be available")
            host_config_result = await tools["get_host_net_config"].ainvoke({"host_name": "pc1"})
            host_config_str = str(host_config_result)
            self.assertTrue(len(host_config_str) > 0, "get_host_net_config must return non-empty output")

            self.assertIn("exec_shell", tools, "exec_shell tool must be available")
            exec_result = await tools["exec_shell"].ainvoke({"host_name": "pc1", "command": "hostname"})
            exec_str = str(exec_result)
            self.assertTrue(len(exec_str) > 0, "exec_shell must return non-empty output")

            return {
                "reachability": reach_str,
                "host_net_config": host_config_str,
                "exec_shell": exec_str,
            }

        results = asyncio.run(_run())

        for key, output in results.items():
            self.assertNotIn(
                "NIKA_SESSION_ID is not set",
                output,
                f"{key}: NIKA_SESSION_ID was not propagated to MCP subprocess",
            )
            self.assertNotIn(
                "Session",
                output[:50] if "not running" in output else "",
                f"{key}: session was not found in subprocess",
            )

    def test_step_06_submit_via_mcp(self) -> None:
        """task_mcp_server.submit() resolves NIKA_SESSION_ID and writes submission.json."""
        self.assertIsNotNone(self.session_id)
        self.assertIsNotNone(self.session_dir)

        config = MCPServerConfig(session_id=self.session_id).load_config(if_submit=True)

        async def _run() -> str:
            client = MultiServerMCPClient(connections=config)
            tools = {t.name: t for t in await client.get_tools()}

            self.assertIn("list_avail_problems", tools)
            self.assertIn("submit", tools)

            avail_raw = await tools["list_avail_problems"].ainvoke({})
            avail = _tool_text_list(avail_raw)
            self.assertTrue(len(avail) > 0, "list_avail_problems must return at least one entry")
            self.assertIn(PROBLEM, avail, f"{PROBLEM} must be among available problems")

            submit_result = await tools["submit"].ainvoke(
                {
                    "is_anomaly": True,
                    "faulty_devices": ["pc1"],
                    "root_cause_name": [PROBLEM],
                }
            )
            return str(submit_result)

        result_str = asyncio.run(_run())
        self.assertIn("success", result_str.lower(), f"submit tool should report success; got: {result_str}")

        submission_path = self.session_dir / "submission.json"
        self.assertTrue(
            submission_path.exists(),
            f"submission.json not found at {submission_path}",
        )
        self.assertIn(
            self.session_id,
            str(submission_path),
            "submission.json path must contain session_id",
        )

        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        self.assertIn("is_anomaly", submission)
        self.assertIn("faulty_devices", submission)
        self.assertIn("root_cause_name", submission)
        self.assertTrue(submission["is_anomaly"])
        self.assertIn("pc1", submission["faulty_devices"])
        self.assertIn(PROBLEM, submission["root_cause_name"])

    def test_step_07_run_mock_agent(self) -> None:
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

        self.assertTrue((self.session_dir / "ground_truth.json").exists())
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

        submission_path = self.session_dir / "submission.json"
        self.assertIn(
            self.session_id,
            str(submission_path),
            "submission.json must be written via MCP to the session-scoped path",
        )

        submission = self._load_json("submission.json")
        for field in ("is_anomaly", "faulty_devices", "root_cause_name"):
            self.assertIn(field, submission)

        run = self._load_json("run.json")
        self.assertEqual(run["session_id"], self.session_id)
        self.assertEqual(run["agent_type"], "mock")

    def test_step_08_session_close(self) -> None:
        """Close the session before offline evaluation."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["session", "close", self.session_id, "-y"])
        type(self).env_destroyed = True

        run = self._load_json("run.json")
        self.assertEqual(run["status"], "finished")

        ps_output = self.runner.invoke(app, ["env", "ps"])
        self.assertEqual(ps_output.exit_code, 0, ps_output.output)
        self.assertNotIn(self.session_id, ps_output.output)

        with self.assertRaises(FileNotFoundError):
            SessionStore().get_session(self.session_id)
        self.assertFalse((Path(SESSIONS_DIR) / f"{self.session_id}.json").exists())

    def test_step_09_eval_metrics(self) -> None:
        """Compute rule-based scores from ground truth and submission on the closed session."""
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

        run = self._load_json("run.json")
        self.assertIn("eval_metrics", run)

    def test_step_10_eval_publish_and_summary(self) -> None:
        """Publish eval artifacts and build a summary CSV offline."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["eval", "publish", "--session-id", self.session_id])

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
        self.assertEqual(rows[0]["root_cause_category"], "link_failure")

        metrics = self._load_json("eval_metrics.json")
        self.assertEqual(float(rows[0]["detection_score"]), metrics["detection_score"])
        self.assertEqual(int(rows[0]["tool_calls"]), metrics["tool_calls"])

        ps_output = self.runner.invoke(app, ["env", "ps"])
        self.assertEqual(ps_output.exit_code, 0, ps_output.output)
        self.assertNotIn(self.session_id, ps_output.output)


if __name__ == "__main__":
    unittest.main()
