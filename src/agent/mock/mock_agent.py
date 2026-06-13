"""Mock LLM agent that simulates BasicReActAgent behaviour without a real LLM.

The agent mirrors the two-phase architecture of BasicReActAgent:
  1. diagnosis phase  – calls Kathara MCP tools and emits a deterministic report
  2. submission phase – calls list_avail_problems + submit via task MCP server

It can be selected via ``nika agent run -a mock`` and is intended for integration
tests and CI pipelines that must exercise the full session pipeline without
standing up a real LLM endpoint.
"""

import json
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.utils.mcp_servers import MCPServerConfig
from nika.utils.session import Session

MOCK_DIAGNOSIS_TOOL_CALLS: list[tuple[str, dict[str, Any]]] = [
    ("get_reachability", {}),
    ("ping_pair", {"host_a": "pc1", "host_b": "pc2"}),
    ("frr_show_ip_route", {"router_name": "r1"}),
]

MOCK_DIAGNOSIS_REPORT = (
    "Anomaly detected: high packet loss between pc1 and pc2.  "
    "BGP routes on r1 show an unreachable prefix (10.0.1.0/24).  "
    "Suspected root cause: link failure on the path between r1 and pc2."
)


def _tool_text_list(result: object) -> list[str]:
    """Normalize MCP tool output into plain strings."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return [result]
    if not isinstance(result, list):
        return [str(result)]

    texts: list[str] = []
    for item in result:
        if isinstance(item, dict) and "text" in item:
            texts.append(str(item["text"]))
        else:
            texts.append(str(item))
    return texts


class MockAgent:
    """Deterministic mock agent that mirrors the BasicReActAgent interface."""

    def __init__(
        self,
        session_id: str,
        llm_backend: str = "mock",
        model: str = "mock-v1",
        max_steps: int = 20,
    ) -> None:
        self.session_id = session_id
        self.llm_backend = llm_backend
        self.model = model
        self.max_steps = max_steps
        self.session = Session()
        self.session.load_running_session(session_id=session_id)

    def load_session(self) -> None:
        self.session.load_running_session(session_id=self.session_id)

    async def run(self, task_description: str) -> dict[str, Any]:
        self.load_session()
        diagnosis_report = await self._run_diagnosis(task_description)
        await self._run_submission(diagnosis_report)
        return {"diagnosis_report": diagnosis_report}

    async def _run_diagnosis(self, task_description: str) -> str:
        logger = self._make_logger("diagnosis_agent")
        logger._log(
            "llm_start",
            {
                "messages": {"role": "user", "content": task_description},
                "model": {"name": self.model, "backend": self.llm_backend},
            },
        )

        mcp_config = MCPServerConfig(session_id=self.session_id)
        diagnosis_config = {
            k: v
            for k, v in mcp_config.load_config(if_submit=False).items()
            if k in ("kathara_base_mcp_server", "kathara_frr_mcp_server")
        }

        client = MultiServerMCPClient(connections=diagnosis_config)
        tools = {tool.name: tool for tool in await client.get_tools()}

        for tool_name, tool_input in MOCK_DIAGNOSIS_TOOL_CALLS:
            logger._log(
                "tool_start",
                {"tool": {"name": tool_name}, "input": json.dumps(tool_input)},
            )
            tool_output = await tools[tool_name].ainvoke(tool_input)
            logger._log(
                "tool_end",
                {
                    "output": str(tool_output),
                    "output_type": type(tool_output).__name__,
                },
            )

        logger._log("llm_end", {"text": MOCK_DIAGNOSIS_REPORT})
        return MOCK_DIAGNOSIS_REPORT

    async def _run_submission(self, diagnosis_report: str) -> None:
        logger = self._make_logger("submission_agent")

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

        config = MCPServerConfig(session_id=self.session_id).load_config(if_submit=True)

        client = MultiServerMCPClient(connections=config)
        tools = {tool.name: tool for tool in await client.get_tools()}

        logger._log("tool_start", {"tool": {"name": "list_avail_problems"}, "input": "{}"})
        avail_raw = await tools["list_avail_problems"].ainvoke({})
        avail = _tool_text_list(avail_raw)
        session_root_cause = getattr(self.session, "root_cause_name", None)
        if session_root_cause in avail:
            mock_root_cause = session_root_cause
        else:
            mock_root_cause = avail[0] if avail else "link_down"
        logger._log(
            "tool_end",
            {"output": json.dumps(avail[:5]) + " ...", "output_type": "list"},
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
        submit_result = await tools["submit"].ainvoke(submission)
        logger._log(
            "tool_end",
            {"output": str(submit_result), "output_type": type(submit_result).__name__},
        )

        logger._log(
            "llm_end",
            {"text": f"Submitted: root cause = {mock_root_cause}, faulty device = pc1"},
        )

    def _make_logger(self, agent_name: str):
        """Return an AgentCallbackLogger for *agent_name*."""
        from agent.utils.loggers import AgentCallbackLogger  # noqa: PLC0415

        return AgentCallbackLogger(agent=agent_name, session_dir=self.session.session_dir)
