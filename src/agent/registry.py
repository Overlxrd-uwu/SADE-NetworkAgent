"""Agent type registry used by ``nika agent run``."""

from typing import Any

from agent.cli.agent import CliAgent
from agent.langgraph.react_agent import BasicReActAgent
from agent.mock.mock_agent import MockAgent


def create_agent(
    agent_type: str,
    *,
    session_id: str,
    llm_backend: str,
    model: str,
    max_steps: int = 20,
    reasoning_effort: str | None = None,
    stream_output: bool = True,
) -> Any:
    """Instantiate an agent for ``agent_type``."""
    match agent_type.lower():
        case "react":
            return BasicReActAgent(
                session_id=session_id,
                llm_backend=llm_backend,
                model=model,
                max_steps=max_steps,
            )
        case "mock":
            return MockAgent(
                session_id=session_id,
                llm_backend=llm_backend,
                model=model,
                max_steps=max_steps,
            )
        case "sdk":
            raise ValueError(
                "Agent type 'sdk' is not implemented yet. "
                "See src/agent/README.md for the Claude/Codex SDK path."
            )
        case "cli":
            return CliAgent(
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
                stream_output=stream_output,
            )
        case _:
            raise ValueError(f"Unsupported agent type: {agent_type!r}")
