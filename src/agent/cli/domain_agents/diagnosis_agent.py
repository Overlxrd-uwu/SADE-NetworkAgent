"""Codex CLI-backed diagnosis worker.

Mirrors the role of :class:`~agent.langgraph.domain_agents.DiagnosisAgent`
in the LangChain path: wraps the same troubleshooting prompt and exposes an
async ``run()`` that returns a free-text diagnosis report.
"""

from agent.cli.codex_worker import CodexWorker

# Keep in sync with agent.langgraph.domain_agents.diagnosis_agent.OVERALL_DIAGNOSIS_PROMPT
_DIAGNOSIS_SYSTEM = """\
You are a network troubleshooting expert.
Focus on (1) detecting if there is an anomaly, (2) localizing the faulty devices, and (3) identifying the root cause.

Basic requirements:
- Use the provided MCP tools to gather necessary information.
- Do not provide mitigation unless explicitly required.
- Rely only on the MCP tools available to you; do not execute arbitrary shell commands.\
"""


class CliDiagnosisAgent:
    """Runs network fault diagnosis via a ``codex exec`` subprocess.

    Parameters
    ----------
    session_id:
        NIKA session identifier.
    session_dir:
        Absolute path to the session results directory.
    model:
        Codex model name (e.g. ``"gpt-5.4-mini"``).
    reasoning_effort:
        Optional Codex ``model_reasoning_effort`` override.
    timeout:
        Hard timeout in seconds for the subprocess.
    scenario_name:
        Scenario identifier used to select relevant Kathara MCP servers.
    problem_names:
        Problem identifiers used together with *scenario_name* for server selection.
    """

    def __init__(
        self,
        session_id: str,
        session_dir: str,
        model: str = "gpt-5.4-mini",
        reasoning_effort: str | None = None,
        timeout: int = 600,
        scenario_name: str = "",
        problem_names: list[str] | None = None,
        *,
        stream_output: bool = True,
    ) -> None:
        self._worker = CodexWorker(
            session_id=session_id,
            session_dir=session_dir,
            phase="diagnosis",
            model=model,
            reasoning_effort=reasoning_effort,
            timeout=timeout,
            scenario_name=scenario_name,
            problem_names=problem_names or [],
            stream_output=stream_output,
        )

    async def run(self, task_description: str) -> str:
        """Return a free-text diagnosis report produced by ``codex exec``."""
        prompt = f"{_DIAGNOSIS_SYSTEM}\n\nTask: {task_description}"
        return await self._worker.run(prompt)
