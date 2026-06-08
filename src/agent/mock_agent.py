"""Mock LLM agent that simulates BasicReActAgent behaviour without a real LLM or MCP servers.

The agent mirrors the two-phase architecture of BasicReActAgent:
  1. diagnosis phase  – simulates several tool calls and emits a diagnosis report
  2. submission phase – calls list_avail_problems + submit, writes submission.json

It can be selected via ``nika agent run -a mock`` and is intended for integration
tests and CI pipelines that must exercise the full session pipeline without
standing up Kathará labs or calling a real LLM endpoint.
"""

import asyncio
import json
import os
from typing import Any

from nika.utils.session import Session

MOCK_DIAGNOSIS_TOOLS: list[tuple[str, str, str]] = [
    (
        "get_reachability",
        '{"device": "pc1"}',
        "UNREACHABLE: pc1 → pc2 — 0/3 packets received (100 % loss)",
    ),
    (
        "ping_pair",
        '{"src": "pc1", "dst": "pc2"}',
        "PING pc1 → pc2: rtt min/avg/max = — ms  (100 % packet loss)",
    ),
    (
        "frr_show_ip_route",
        '{"device": "r1"}',
        "B>* 10.0.0.0/24 [20/0] via 192.168.1.1, eth0, 00:01:23\n"
        "B>* 10.0.1.0/24 unreachable",
    ),
]

MOCK_DIAGNOSIS_REPORT = (
    "Anomaly detected: high packet loss between pc1 and pc2.  "
    "BGP routes on r1 show an unreachable prefix (10.0.1.0/24).  "
    "Suspected root cause: link failure on the path between r1 and pc2."
)


class MockAgent:
    """Deterministic mock agent that mirrors the BasicReActAgent interface."""

    def __init__(
        self,
        llm_backend: str = "mock",
        model: str = "mock-v1",
        max_steps: int = 20,
    ) -> None:
        self.llm_backend = llm_backend
        self.model = model
        self.max_steps = max_steps

    def load_session(self) -> None:
        self.session = Session()
        self.session.load_running_session(session_id=os.getenv("NIKA_SESSION_ID"))

    async def run(self, task_description: str) -> dict[str, Any]:
        self.load_session()
        diagnosis_report = await self._run_diagnosis(task_description)
        await self._run_submission(diagnosis_report)
        return {"diagnosis_report": diagnosis_report}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_diagnosis(self, task_description: str) -> str:
        logger = self._make_logger("diagnosis_agent")
        logger._log(
            "llm_start",
            {
                "messages": {"role": "user", "content": task_description},
                "model": {"name": self.model, "backend": self.llm_backend},
            },
        )

        for tool_name, tool_input, tool_output in MOCK_DIAGNOSIS_TOOLS:
            logger._log("tool_start", {"tool": {"name": tool_name}, "input": tool_input})
            await asyncio.sleep(0)
            logger._log("tool_end", {"output": tool_output, "output_type": "str"})

        logger._log("llm_end", {"text": MOCK_DIAGNOSIS_REPORT})
        return MOCK_DIAGNOSIS_REPORT

    async def _run_submission(self, diagnosis_report: str) -> None:
        from nika.orchestrator.problems.prob_pool import list_avail_problem_names  # noqa: PLC0415

        logger = self._make_logger("submission_agent")
        avail_problems = list_avail_problem_names()
        mock_root_cause = avail_problems[0] if avail_problems else "link_down"

        logger._log(
            "llm_start",
            {
                "messages": {
                    "role": "user",
                    "content": (
                        f"Based on diagnosis: {diagnosis_report}. "
                        "Please call list_avail_problems and then submit."
                    ),
                },
                "model": {"name": self.model, "backend": self.llm_backend},
            },
        )

        logger._log("tool_start", {"tool": {"name": "list_avail_problems"}, "input": "{}"})
        await asyncio.sleep(0)
        logger._log(
            "tool_end",
            {"output": json.dumps(avail_problems[:5]) + " ...", "output_type": "list"},
        )

        submission: dict[str, Any] = {
            "is_anomaly": True,
            "faulty_devices": ["pc1"],
            "root_cause_name": [mock_root_cause],
        }
        logger._log(
            "tool_start",
            {"tool": {"name": "submit"}, "input": json.dumps(submission)},
        )
        await asyncio.sleep(0)
        self._write_submission(submission)
        logger._log("tool_end", {"output": "Submission success.", "output_type": "str"})

        logger._log(
            "llm_end",
            {"text": f"Submitted: root cause = {mock_root_cause}, faulty device = pc1"},
        )

    def _write_submission(self, submission: dict[str, Any]) -> None:
        """Write submission.json into the session directory."""
        session_dir = self.session.session_dir
        os.makedirs(session_dir, exist_ok=True)
        with open(os.path.join(session_dir, "submission.json"), "w", encoding="utf-8") as fh:
            json.dump(submission, fh, indent=2)

    def _make_logger(self, agent_name: str):
        """Return an AgentCallbackLogger for *agent_name*."""
        from agent.utils.loggers import AgentCallbackLogger  # noqa: PLC0415

        return AgentCallbackLogger(agent=agent_name)
