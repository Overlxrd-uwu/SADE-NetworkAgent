"""Codex CLI agent pipeline integration test and display helpers.

Runs the full troubleshooting pipeline using the ``CliAgent`` adapter:

    env run (simple_bgp)
      → failure inject (link_down on pc1)
      → agent run -a cli          # Codex CLI subprocess worker
      → check workspace artefacts + codex JSONL display
      → session close
      → eval metrics

Also includes fast unit tests for Codex CLI helpers:

* :func:`agent.cli.codex_display.format_codex_event` — renders ``codex exec --json``
  events logged into ``messages.jsonl``
* :func:`agent.cli.codex_worker._build_mcp_toml` — builds the per-phase MCP
  ``config.toml`` written under ``codex_workspace/.codex_home/``

Session artefacts and the Codex workspace are intentionally **preserved** after the
test so you can inspect them:

    results/<session_id>/
      messages.jsonl          # events from both LangGraph nodes and Codex subprocesses
      submission.json         # written by task MCP server via submit() tool call
      ground_truth.json
      run.json
      codex_workspace/
        .git/                 # git-initialised by CodexWorker so codex is happy
        .codex_home/
          config.toml         # per-session, per-phase MCP server config (TOML)
          auth.json           # symlink → ~/.codex/auth.json
        diagnosis_output.txt  # last assistant message written by codex exec
        submission_output.txt

Prerequisites
-------------
- Docker must be running
- Kathara images must be available (kathara/nika-frr, kathara/nika-base)
- Codex CLI must be installed and authenticated
  (run ``codex login`` or set OPENAI_API_KEY before running the test)

Run
---
    uv run python -m unittest tests/test_cli_agent_pipeline.py -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from agent.cli.codex_display import format_codex_event
from agent.cli.codex_worker import CodexWorker, _build_mcp_toml
from nika.codex_cli.main import app
from nika.utils.session_store import SessionStore
from tests.integration_base import OrderedPipelineTestCase

SCENARIO = "simple_bgp"
PROBLEM = "link_down"
MODEL = "gpt-5.4-mini"


class BuildMcpTomlTest(unittest.TestCase):
    """Unit tests for CodexWorker MCP config generation (no Docker/Codex required)."""

    def test_includes_noninteractive_approval_defaults(self) -> None:
        toml = _build_mcp_toml(
            {
                "kathara_base_mcp_server": {
                    "command": "python3",
                    "args": ["/path/kathara_base_mcp_server.py"],
                    "env": {"NIKA_SESSION_ID": "sess-123"},
                }
            }
        )

        self.assertIn('approval_policy = "never"', toml)
        self.assertIn('sandbox_mode = "workspace-write"', toml)
        self.assertIn('default_tools_approval_mode = "approve"', toml)
        self.assertIn("[mcp_servers.kathara_base_mcp_server]", toml)
        self.assertIn('NIKA_SESSION_ID = "sess-123"', toml)

    def test_approves_each_configured_server(self) -> None:
        toml = _build_mcp_toml(
            {
                "kathara_base_mcp_server": {
                    "command": "python3",
                    "args": ["/path/base.py"],
                },
                "task_mcp_server": {
                    "command": "python3",
                    "args": ["/path/task.py"],
                },
            }
        )

        self.assertEqual(toml.count('default_tools_approval_mode = "approve"'), 2)


class CodexWorkerConfigTest(unittest.TestCase):
    """Unit tests for CodexWorker constructor validation."""

    def test_rejects_invalid_reasoning_effort(self) -> None:
        with self.assertRaises(ValueError):
            CodexWorker(
                session_id="sess-123",
                session_dir="/tmp/sess-123",
                phase="diagnosis",
                reasoning_effort="turbo",
            )


class CodexDisplayTest(unittest.TestCase):
    """Unit tests for Codex JSONL terminal formatting (no Docker/Codex required)."""

    def test_agent_message(self) -> None:
        event = {
            "type": "item.completed",
            "item": {"id": "item_1", "type": "agent_message", "text": "BGP session is down."},
        }
        rendered = format_codex_event(event)
        self.assertIn("BGP session is down.", rendered or "")

    def test_mcp_tool_call_lifecycle(self) -> None:
        started = {
            "type": "item.started",
            "item": {
                "id": "item_2",
                "type": "mcp_tool_call",
                "server": "kathara_frr_mcp_server",
                "tool": "show_bgp_summary",
                "arguments": {"device": "router1"},
                "status": "in_progress",
            },
        }
        completed = {
            "type": "item.completed",
            "item": {
                "id": "item_2",
                "type": "mcp_tool_call",
                "server": "kathara_frr_mcp_server",
                "tool": "show_bgp_summary",
                "status": "completed",
                "result": {"content": [{"type": "text", "text": "neighbor down"}]},
            },
        }
        self.assertIn("show_bgp_summary", format_codex_event(started) or "")
        self.assertIn("neighbor down", format_codex_event(completed) or "")

    def test_turn_completed(self) -> None:
        event = {
            "type": "turn.completed",
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        rendered = format_codex_event(event)
        self.assertIn("in=100", rendered or "")
        self.assertIn("out=20", rendered or "")

    def test_reconnecting_error_is_non_fatal(self) -> None:
        event = {"type": "error", "message": "Reconnecting... 1/5"}
        self.assertIn("Reconnecting", format_codex_event(event) or "")


class CliAgentPipelineTest(OrderedPipelineTestCase):
    """Ordered step tests for the Codex CLI agent adapter."""

    @classmethod
    def tearDownClass(cls) -> None:
        """Undeploy the lab if still running; preserve all session artefacts for inspection."""
        if cls.session_id and not cls.env_destroyed:
            try:
                cls.runner.invoke(app, ["session", "close", cls.session_id, "-y"])
            except Exception:
                pass
        # Intentionally skip _remove_session_results so the codex workspace survives.

    # ------------------------------------------------------------------
    # Step 1 – start environment
    # ------------------------------------------------------------------

    def test_step_01_start_env(self) -> None:
        """Deploy simple_bgp and capture the session id."""
        out = self._invoke_ok(["env", "run", SCENARIO])
        match = re.search(r"session_id=(\S+)", out.strip())
        self.assertIsNotNone(match, f"session_id missing from env run output:\n{out}")
        type(self).session_id = match.group(1)
        self._assert_session_ready(self.session_id, SCENARIO)

    # ------------------------------------------------------------------
    # Step 2 – inject link_down fault
    # ------------------------------------------------------------------

    def test_step_02_inject_failure(self) -> None:
        """Inject a link-down fault and record ground truth."""
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

        row = SessionStore().get_session(self.session_id)
        self.assertIn(PROBLEM, row.get("problem_names", []))
        self.assertIn("task_description", row)
        self.assertTrue(len(row["task_description"]) > 0)

        type(self).session_dir = Path(row["session_dir"])
        self.assertTrue((self.session_dir / "ground_truth.json").exists())

        ground_truth = self._load_json("ground_truth.json")
        self.assertTrue(ground_truth["is_anomaly"])
        self.assertIn(PROBLEM, ground_truth["root_cause_name"])

    # ------------------------------------------------------------------
    # Step 3 – run the CLI agent
    # ------------------------------------------------------------------

    def test_step_03_run_cli_agent(self) -> None:
        """Run the Codex CLI agent through the full diagnosis → submission pipeline.

        This step invokes ``codex exec`` twice (once per phase) against the live lab.
        It may take up to a few minutes depending on model latency.
        """
        self.assertIsNotNone(self.session_id)

        result = self.runner.invoke(
            app,
            [
                "agent",
                "run",
                "--agent",
                "cli",
                "--backend",
                "openai",
                "--model",
                MODEL,
                "--session-id",
                self.session_id,
            ],
        )

        # A non-zero exit code here usually means codex is not authenticated or
        # not installed.  Print the full output for easier debugging.
        self.assertEqual(
            result.exit_code,
            0,
            f"agent run exited {result.exit_code}:\n{result.output}"
            + (f"\nException: {result.exception}" if result.exception else ""),
        )

        row = SessionStore().get_session(self.session_id)
        self.assertEqual(row.get("agent_type"), "cli")
        self.assertEqual(row.get("model"), MODEL)

    # ------------------------------------------------------------------
    # Step 4 – verify intermediate artefacts
    # ------------------------------------------------------------------

    def test_step_04_check_workspace_and_messages(self) -> None:
        """Verify that the Codex workspace and messages.jsonl were written correctly."""
        self.assertIsNotNone(self.session_dir)

        # Codex workspace is isolated from NIKA artefacts in its own subdirectory.
        workspace = self.session_dir / "codex_workspace"
        self.assertTrue(workspace.is_dir(), "codex_workspace/ must exist after agent run")
        self.assertTrue((workspace / ".git").is_dir(), "workspace must be a git repo")

        codex_home = workspace / ".codex_home"
        self.assertTrue(codex_home.is_dir(), "isolated .codex_home must exist")

        # --- diagnosis TOML config ---
        diag_config = codex_home / "config.toml"
        self.assertTrue(diag_config.exists(), "config.toml must be written in .codex_home")
        # config.toml is overwritten each phase; it retains the last phase written
        # (submission), but both phases write one; we check structural correctness.
        config_text = diag_config.read_text(encoding="utf-8")
        self.assertIn("NIKA_SESSION_ID", config_text, "Session ID must appear in the MCP server env block")
        self.assertIn(self.session_id, config_text, "Session ID value must match the running session")
        self.assertIn("[mcp_servers.", config_text, "config.toml must contain at least one [mcp_servers.*] section")
        self.assertIn(
            'default_tools_approval_mode = "approve"',
            config_text,
            "Codex exec needs auto-approved MCP tools in non-interactive mode",
        )

        # --- output files from codex exec ---
        diag_output = workspace / "diagnosis_output.txt"
        self.assertTrue(
            diag_output.exists(),
            "diagnosis_output.txt must be written by --output-last-message",
        )
        self.assertGreater(
            diag_output.stat().st_size,
            0,
            "diagnosis output must be non-empty",
        )

        # --- messages.jsonl ---
        messages_path = self.session_dir / "messages.jsonl"
        self.assertTrue(messages_path.exists(), "messages.jsonl must exist after agent run")

        messages = self._load_jsonl("messages.jsonl")
        agents = {entry["agent"] for entry in messages}
        self.assertIn("diagnosis_agent_cli", agents, "diagnosis phase must log events under 'diagnosis_agent_cli'")
        self.assertIn("submission_agent_cli", agents, "submission phase must log events under 'submission_agent_cli'")

        # MCP config event contains the selected server list
        mcp_events = [e for e in messages if e.get("event") == "mcp_config"]
        self.assertTrue(len(mcp_events) >= 1, "At least one mcp_config event must be logged")
        diag_mcp = next((e for e in mcp_events if e.get("agent") == "diagnosis_agent_cli"), None)
        self.assertIsNotNone(diag_mcp, "diagnosis phase must log an mcp_config event")
        servers = diag_mcp.get("servers", [])
        self.assertIn("kathara_base_mcp_server", servers, "base server must always be selected for diagnosis")
        self.assertIn("kathara_frr_mcp_server", servers, "'simple_bgp' contains 'bgp' → frr server must be selected")
        self.assertNotIn("kathara_bmv2_mcp_server", servers, "bmv2 server must NOT be selected for a pure BGP scenario")
        self.assertNotIn(
            "kathara_telemetry_mcp_server", servers, "telemetry server must NOT be selected for a pure BGP scenario"
        )

        sub_mcp = next((e for e in mcp_events if e.get("agent") == "submission_agent_cli"), None)
        self.assertIsNotNone(sub_mcp, "submission phase must log an mcp_config event")
        self.assertIn("task_mcp_server", sub_mcp.get("servers", []), "task MCP server must be selected for submission")

        # subprocess_start events confirm codex was invoked for both phases
        start_events = [e for e in messages if e.get("event") == "subprocess_start"]
        self.assertGreaterEqual(len(start_events), 2, "subprocess_start must be logged for both phases")

        # --- codex JSONL events must be logged and renderable ---
        codex_events = [entry for entry in messages if "codex_event" in entry]
        self.assertGreater(
            len(codex_events),
            0,
            "messages.jsonl must contain codex exec --json events under 'codex_event'",
        )

        rendered_count = 0
        for entry in codex_events:
            rendered = format_codex_event(entry["codex_event"])
            if rendered:
                rendered_count += 1
        self.assertGreater(
            rendered_count,
            0,
            "at least one codex event from the pipeline must format for terminal display",
        )

        agent_messages = [
            entry
            for entry in codex_events
            if entry["codex_event"].get("type") == "item.completed"
            and (entry["codex_event"].get("item") or {}).get("type") == "agent_message"
        ]
        self.assertTrue(agent_messages, "pipeline must produce at least one agent_message codex event")
        rendered_agent = format_codex_event(agent_messages[0]["codex_event"])
        self.assertIsNotNone(rendered_agent)
        self.assertIn("Agent:", rendered_agent or "")

        mcp_calls = [
            entry
            for entry in codex_events
            if (entry["codex_event"].get("item") or {}).get("type") == "mcp_tool_call"
        ]
        self.assertTrue(mcp_calls, "pipeline must produce at least one mcp_tool_call codex event")
        rendered_mcp = format_codex_event(mcp_calls[0]["codex_event"])
        self.assertIsNotNone(rendered_mcp)
        self.assertIn("MCP", rendered_mcp or "")

        turn_completed = [entry for entry in codex_events if entry["codex_event"].get("type") == "turn.completed"]
        self.assertTrue(turn_completed, "pipeline must produce at least one turn.completed codex event")
        rendered_turn = format_codex_event(turn_completed[0]["codex_event"])
        self.assertIsNotNone(rendered_turn)
        self.assertIn("Turn completed", rendered_turn or "")

    # ------------------------------------------------------------------
    # Step 5 – verify submission (written by task MCP server)
    # ------------------------------------------------------------------

    def test_step_05_check_submission(self) -> None:
        """submission.json must exist and contain the required fields."""
        self.assertIsNotNone(self.session_dir)

        submission_path = self.session_dir / "submission.json"
        self.assertTrue(
            submission_path.exists(),
            "submission.json must be written by the task MCP server's submit() tool.\n"
            "If this fails, codex did not complete the submission phase — check "
            "messages.jsonl for subprocess_error events.",
        )

        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        for field in ("is_anomaly", "faulty_devices", "root_cause_name"):
            self.assertIn(field, submission, f"submission.json must contain '{field}'")

    # ------------------------------------------------------------------
    # Step 6 – close session
    # ------------------------------------------------------------------

    def test_step_06_session_close(self) -> None:
        """Undeploy the lab and mark the session as finished."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["session", "close", self.session_id, "-y"])
        type(self).env_destroyed = True

        run = self._load_json("run.json")
        self.assertEqual(run["status"], "finished")
        self.assertEqual(run["agent_type"], "cli")

    # ------------------------------------------------------------------
    # Step 7 – evaluate metrics on the closed session
    # ------------------------------------------------------------------

    def test_step_07_eval_metrics(self) -> None:
        """Compute rule-based evaluation scores from ground truth and submission."""
        self.assertIsNotNone(self.session_id)

        self._invoke_ok(["eval", "metrics", "--session-id", self.session_id])

        metrics_path = self.session_dir / "eval_metrics.json"
        self.assertTrue(metrics_path.exists(), "eval_metrics.json must be written")

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for field in ("detection_score", "localization_accuracy", "rca_accuracy", "tool_calls"):
            self.assertIn(field, metrics, f"eval_metrics.json must contain '{field}'")

        self.assertGreaterEqual(metrics["detection_score"], 0.0)
        # tool_calls counts MCP tool invocations in messages.jsonl for the diagnosis agent.
        self.assertGreater(metrics["tool_calls"], 0)

        run = self._load_json("run.json")
        self.assertIn("eval_metrics", run, "run.json must be updated with eval_metrics after nika eval metrics")


if __name__ == "__main__":
    unittest.main()
