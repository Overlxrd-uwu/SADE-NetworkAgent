"""Placeholder for the Claude / Codex SDK agent.

Select with ``nika agent run -a sdk`` once implemented.
"""

from typing import Any


class SdkAgent:
    """Two-phase troubleshooting agent backed by Claude or Codex SDK."""

    def __init__(
        self,
        session_id: str,
        llm_backend: str = "claude",
        model: str = "claude-sonnet-4-20250514",
        max_steps: int = 20,
    ) -> None:
        self.session_id = session_id
        self.llm_backend = llm_backend
        self.model = model
        self.max_steps = max_steps

    async def run(self, task_description: str) -> dict[str, Any]:
        raise NotImplementedError(
            "SdkAgent is not implemented yet. "
            "Implement agent.sdk.agent.SdkAgent and register it in agent.registry."
        )
