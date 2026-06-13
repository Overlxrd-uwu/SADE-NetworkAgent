"""Run a troubleshooting agent against the current session task."""

import asyncio
import logging

from agent.mock_agent import MockAgent
from agent.react_agent import BasicReActAgent
from nika.utils.logger import bind_session_dir, log_event
from nika.utils.session import Session

logging.basicConfig(level=logging.INFO)


def _agent_selector(
    agent_type: str,
    llm_backend: str,
    model: str,
    *,
    session_id: str,
    max_steps: int = 20,
):
    """Return an agent instance for ``agent_type`` or None if unsupported."""
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
        case _:
            return None


def start_agent(
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    *,
    session_id: str | None = None,
) -> None:
    """Load the running session, run the agent on ``task_description``, then end the session."""
    session = Session()
    session.load_running_session(session_id=session_id)
    session.update_session("agent_type", agent_type)
    session.update_session("llm_backend", llm_backend)
    session.update_session("model", model)
    session.start_session()

    bind_session_dir(session.session_dir)
    log_event(
        "agent_start",
        f"Starting agent: {agent_type} (model={model}) in session {session.session_id}",
        session_id=session.session_id,
        agent_type=agent_type,
        model=model,
    )
    agent = _agent_selector(
        agent_type,
        llm_backend,
        model,
        session_id=session.session_id,
        max_steps=max_steps,
    )
    if agent is None:
        raise ValueError(f"Unsupported agent type: {agent_type!r}")
    asyncio.run(agent.run(task_description=session.task_description))

    session.end_session()
    log_event(
        "agent_end",
        f"Agent run completed for session {session.session_id}",
        session_id=session.session_id,
        agent_type=agent_type,
    )
