"""Codex CLI-backed submission worker.

Mirrors the role of :class:`~agent.langgraph.domain_agents.SubmissionAgent`
in the LangChain path: calls the task MCP server's ``submit`` tool to record
a structured result based on the diagnosis report.
"""

from textwrap import dedent

from agent.cli.codex_worker import CodexWorker

# Keep in sync with agent.langgraph.domain_agents.submission_agent.SUBMIT_PROMPT_TEMPLATE
_SUBMISSION_SYSTEM = dedent("""\
    You are an expert network engineer.
    Your task is to submit the final solution for this network problem based on the diagnosis report provided.
    Carefully review the diagnosis results and ensure that your submission is accurate and complete.
    You must strictly follow the submission format and call the submit() MCP tool to submit your solution.
    Rely only on the MCP tools available to you; do not execute arbitrary shell commands.\
""")


class CliSubmissionAgent:
    """Calls the task MCP server's ``submit`` tool via a ``codex exec`` subprocess.

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
    """

    def __init__(
        self,
        session_id: str,
        session_dir: str,
        model: str = "gpt-5.4-mini",
        reasoning_effort: str | None = None,
        timeout: int = 300,
        *,
        stream_output: bool = True,
    ) -> None:
        self._worker = CodexWorker(
            session_id=session_id,
            session_dir=session_dir,
            phase="submission",
            model=model,
            reasoning_effort=reasoning_effort,
            timeout=timeout,
            stream_output=stream_output,
        )

    async def run(self, diagnosis_report: str) -> str:
        """Submit the diagnosis result via the task MCP server.

        Parameters
        ----------
        diagnosis_report:
            Free-text output from the diagnosis phase.  Forwarded verbatim
            to the Codex CLI so it can extract the structured answer and call
            ``submit()``.
        """
        prompt = (
            f"{_SUBMISSION_SYSTEM}\n\n"
            f"Based on the diagnosis report: {diagnosis_report}\n"
            "Please provide the submission. Do not submit if no report is available."
        )
        return await self._worker.run(prompt)
