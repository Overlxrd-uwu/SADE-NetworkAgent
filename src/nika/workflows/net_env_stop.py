"""Stop the Kathara lab for the current session and clear runtime state."""

from datetime import datetime

from nika.net_env.net_env_pool import get_net_env_instance
from nika.utils.logger import log_event
from nika.utils.session import Session
from nika.utils.session_store import SessionStore


def _stop_session_record(session_meta: dict) -> None:
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

    if net_env.lab_exists():
        net_env.undeploy()
        log_event(
            "env_stop",
            f"Stopped network environment: {scenario} ({session.session_id})",
            scenario=scenario,
            session_id=session.session_id,
        )
    else:
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


def stop_net_env(session_id: str | None = None, *, stop_all: bool = False) -> None:
    """Undeploy one or all running labs and update session status."""
    store = SessionStore()
    running = store.list_running_sessions()
    if not running:
        raise FileNotFoundError("No running session found. Run `nika env run <scenario>` first.")

    if stop_all:
        for session_meta in running:
            _stop_session_record(session_meta)
        return

    if session_id is None:
        session = Session()
        session.load_running_session(session_id=None)
        _stop_session_record(store.get_session(session.session_id))
        return

    target = store.get_session(session_id)
    if target.get("status") != "running":
        raise ValueError(f"Session '{session_id}' is not running.")
    _stop_session_record(target)
