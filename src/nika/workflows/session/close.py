"""Close running sessions: undeploy lab, end failures, clear runtime state."""

from datetime import datetime

from Kathara.manager.Kathara import Kathara

from nika.net_env.net_env_pool import get_net_env_instance
from nika.utils.logger import bind_session_dir, log_event
from nika.utils.session import Session
from nika.utils.session_resolve import resolve_running_session_id
from nika.utils.session_store import SessionStore


def wipe_kathara_labs() -> None:
    """Remove all Kathara devices and collision domains for the current user."""
    Kathara.get_instance().wipe()


def _stop_session_record(session_meta: dict, *, undeploy: bool = True) -> None:
    session = Session()
    for key, value in session_meta.items():
        setattr(session, key, value)
    scenario = session.scenario_name
    if not scenario:
        raise ValueError("Session has no scenario_name; cannot determine which lab to stop.")

    net_env_kwargs = {}
    if getattr(session, "scenario_topo_size", None) is not None:
        net_env_kwargs["topo_size"] = session.scenario_topo_size
    if getattr(session, "lab_name", None):
        net_env_kwargs["lab_name"] = session.lab_name
    net_env = get_net_env_instance(scenario, **net_env_kwargs)

    session_dir = session_meta.get("session_dir")
    if not session_dir:
        raise ValueError(f"Session '{session.session_id}' has no session_dir.")
    bind_session_dir(session_dir)

    if undeploy and net_env.lab_exists():
        net_env.undeploy()
        log_event(
            "env_stop",
            f"Stopped network environment: {scenario} ({session.session_id})",
            scenario=scenario,
            session_id=session.session_id,
        )
    elif undeploy:
        log_event(
            "env_stop_skipped",
            f"Network environment {scenario} ({session.session_id}) is not deployed.",
            scenario=scenario,
            session_id=session.session_id,
        )

    ended_cnt = SessionStore().mark_session_failures_ended(
        session.session_id, end_time=datetime.now().timestamp()
    )
    if ended_cnt:
        log_event(
            "failures_ended",
            f"Marked {ended_cnt} failure record(s) as ended for session {session.session_id}",
            session_id=session.session_id,
            count=ended_cnt,
        )

    session.clear_session()
    log_event(
        "session_cleared",
        f"Cleared session {session.session_id} for scenario {scenario}",
        session_id=session.session_id,
        scenario=scenario,
    )


def close_session(
    session_id: str | None = None,
    *,
    undeploy: bool = True,
    stop_all: bool = False,
) -> None:
    """Close one or all running sessions and clear runtime state."""
    store = SessionStore()
    running = store.list_running_sessions()

    if stop_all:
        try:
            for session_meta in running:
                _stop_session_record(session_meta, undeploy=undeploy)
        finally:
            if undeploy:
                wipe_kathara_labs()
        return

    if not running:
        raise FileNotFoundError("No running session found. Run `nika env run <scenario>` first.")

    resolved_id = resolve_running_session_id(session_id, store=store)
    _stop_session_record(store.get_session(resolved_id), undeploy=undeploy)
