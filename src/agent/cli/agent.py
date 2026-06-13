"""LangGraph + Codex CLI agent.

Reuses the same :class:`~langgraph.graph.StateGraph` structure as
:class:`~agent.langgraph.react_agent.BasicReActAgent` but replaces the
LangChain ReAct workers with Codex CLI subprocess wrappers:

* **diagnosis node** → :class:`~agent.cli.domain_agents.CliDiagnosisAgent`
  (``codex exec`` with Kathara MCP servers; server set chosen dynamically
  based on the session scenario)
* **submission node** → :class:`~agent.cli.domain_agents.CliSubmissionAgent`
  (``codex exec`` with the task MCP server; calls ``submit()`` to record
  a structured result)

Session ID propagation follows the same path as the LangChain path:
``NIKA_SESSION_ID`` is injected into each MCP server's ``env`` block via
:class:`~agent.utils.mcp_servers.MCPServerConfig`.

Select with ``nika agent run -a cli``.
"""

import logging
import os
import sys
from typing import Any

import langsmith as ls
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from pydantic import Field
from typing_extensions import TypedDict

from agent.cli.domain_agents.diagnosis_agent import CliDiagnosisAgent
from agent.cli.domain_agents.submission_agent import CliSubmissionAgent
from agent.utils.loggers import MessageLogger
from nika.utils.session import Session

logging.basicConfig(level=logging.INFO)


class AgentState(TypedDict):
    """Shared state passed between LangGraph nodes."""

    messages: list[BaseMessage]
    diagnosis_report: str = Field(default="")
    is_max_steps_reached: bool = Field(default=False)


class CliAgent:
    """Two-phase troubleshooting agent: LangGraph orchestration + Codex CLI workers.

    Parameters
    ----------
    session_id:
        NIKA session identifier.
    model:
        Codex model name forwarded to ``codex exec -m`` (default ``"gpt-5.4-mini"``).
    reasoning_effort:
        Codex ``model_reasoning_effort`` override (``none``, ``minimal``, ``low``,
        ``medium``, ``high``, ``xhigh``).  When omitted, Codex uses its default.
    """

    def __init__(
        self,
        session_id: str,
        model: str = "gpt-5.4-mini",
        reasoning_effort: str | None = None,
        *,
        stream_output: bool = True,
    ) -> None:
        self.session_id = session_id
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._stream_output = stream_output

        session = Session()
        session.load_running_session(session_id=session_id)
        self.session = session
        self.session_dir: str = session.session_dir

        scenario_name: str = getattr(session, "scenario_name", "")
        problem_names: list[str] = getattr(session, "problem_names", [])

        self._diagnosis_agent = CliDiagnosisAgent(
            session_id=session_id,
            session_dir=self.session_dir,
            model=model,
            reasoning_effort=reasoning_effort,
            scenario_name=scenario_name,
            problem_names=problem_names,
            stream_output=stream_output,
        )
        self._submission_agent = CliSubmissionAgent(
            session_id=session_id,
            session_dir=self.session_dir,
            model=model,
            reasoning_effort=reasoning_effort,
            stream_output=stream_output,
        )

        builder = StateGraph(AgentState)
        builder.add_node("diagnosis_agent", self._run_diagnosis)
        builder.add_node("submission_agent", self._run_submission)
        builder.add_edge(START, "diagnosis_agent")
        builder.add_conditional_edges(
            "diagnosis_agent",
            lambda state: state.get("is_max_steps_reached", False),
            {True: END, False: "submission_agent"},
        )
        builder.add_edge("submission_agent", END)
        self.graph = builder.compile()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, task_description: str) -> dict[str, Any]:
        """Execute the two-phase pipeline and return the final graph state."""
        with ls.tracing_context(
            project_name=os.getenv("LANGSMITH_PROJECT", "NIKA"),
            metadata={
                "scenario": getattr(self.session, "scenario_name", ""),
                "problem": getattr(self.session, "problem_names", [""])[0],
                "topo_size": getattr(self.session, "scenario_topo_size", ""),
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
                "agent": "cli",
            },
        ):
            return await self.graph.ainvoke(
                {"messages": [HumanMessage(content=task_description)]}
            )

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    async def _run_diagnosis(self, state: AgentState) -> dict[str, Any]:
        task_description: str = state["messages"][-1].content
        logger = MessageLogger(agent="diagnosis_agent_cli", session_dir=self.session_dir)
        self._print_phase("diagnosis", "starting network fault analysis")
        logger.log("agent_start", {"phase": "diagnosis", "task_preview": task_description[:200]})

        try:
            report = await self._diagnosis_agent.run(task_description)
        except Exception as exc:
            logger.log("agent_error", {"phase": "diagnosis", "error": str(exc)})
            return {
                "diagnosis_report": f"ERROR: {exc}",
                "is_max_steps_reached": False,
            }

        is_error = report.startswith("ERROR:")
        logger.log("agent_done", {"phase": "diagnosis", "is_error": is_error, "report_length": len(report)})
        self._print_phase("diagnosis", "completed" if not is_error else f"finished with error ({report[:120]})")
        return {
            "diagnosis_report": report,
            "is_max_steps_reached": False,
        }

    async def _run_submission(self, state: AgentState) -> dict[str, Any]:
        diagnosis_report: str = state["diagnosis_report"]
        logger = MessageLogger(agent="submission_agent_cli", session_dir=self.session_dir)
        self._print_phase("submission", "recording structured result")
        logger.log("agent_start", {"phase": "submission"})

        try:
            result = await self._submission_agent.run(diagnosis_report)
        except Exception as exc:
            logger.log("agent_error", {"phase": "submission", "error": str(exc)})
            return {"messages": state["messages"]}

        logger.log("agent_done", {"phase": "submission", "result_length": len(result)})
        self._print_phase("submission", "completed")
        return {"messages": [*state["messages"], HumanMessage(content=result)]}

    def _print_phase(self, phase: str, message: str) -> None:
        if not self._stream_output:
            return
        banner = f" [{phase.upper()}] {message} "
        width = max(60, len(banner) + 4)
        print(f"\n{'=' * width}", file=sys.stderr, flush=True)
        print(banner.center(width), file=sys.stderr, flush=True)
        print(f"{'=' * width}\n", file=sys.stderr, flush=True)
