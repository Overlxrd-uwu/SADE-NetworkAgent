"""Run a troubleshooting agent against the current session task."""

import asyncio
import logging

from agent.registry import create_agent
from nika.utils.logger import bind_session_dir, log_event
from nika.utils.session import Session

logging.basicConfig(level=logging.INFO)


def start_agent(
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    *,
    session_id: str | None = None,
    reasoning_effort: str | None = None,
    stream_output: bool = True,
) -> None:
    """Load the running session, run the agent on ``task_description``, then end the session."""
    session = Session()
    session.load_running_session(session_id=session_id)
    session.update_session("agent_type", agent_type)
    session.update_session("llm_backend", llm_backend)
    session.update_session("model", model)
    if reasoning_effort is not None:
        session.update_session("reasoning_effort", reasoning_effort)
    session.start_session()

    bind_session_dir(session.session_dir)
    log_event(
        "agent_start",
        f"Starting agent: {agent_type} (model={model}) in session {session.session_id}",
        session_id=session.session_id,
        agent_type=agent_type,
        model=model,
    )
    if agent_type == "cli" and stream_output:
        effort_line = f" | Reasoning effort: {reasoning_effort}" if reasoning_effort else ""
        print(
            f"Session {session.session_id}\n"
            f"Agent: cli | Model: {model}{effort_line}\n"
            f"Results: {session.session_dir}\n",
            flush=True,
        )
    agent = create_agent(
        agent_type,
        session_id=session.session_id,
        llm_backend=llm_backend,
        model=model,
        max_steps=max_steps,
        reasoning_effort=reasoning_effort,
        stream_output=stream_output,
    )
    asyncio.run(agent.run(task_description=session.task_description))

    session.end_session()
    log_event(
        "agent_end",
        f"Agent run completed for session {session.session_id}",
        session_id=session.session_id,
        agent_type=agent_type,
    )
    if agent_type == "cli" and stream_output:
        print(f"\nDone. Results saved to {session.session_dir}\n", flush=True)
