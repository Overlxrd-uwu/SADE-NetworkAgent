"""LangGraph + Codex CLI agents.

Same two-phase orchestration as ``agent.langgraph.react_agent.BasicReActAgent``,
but worker nodes invoke ``codex exec`` subprocesses instead of LangChain
``create_agent`` graphs.

Layout::

    cli/
      agent.py                    # CliAgent — StateGraph orchestrator
      codex_worker.py             # CodexWorker — subprocess adapter
      domain_agents/
        diagnosis_agent.py        # CliDiagnosisAgent
        submission_agent.py       # CliSubmissionAgent
"""

from agent.cli.agent import CliAgent

__all__ = ["CliAgent"]
