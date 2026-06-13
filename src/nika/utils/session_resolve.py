"""Resolve runtime session ids for CLI commands and workflows."""

from __future__ import annotations

from nika.utils.session_store import SessionStore


def resolve_session_id(
    session_id: str | None = None,
    *,
    store: SessionStore | None = None,
) -> str:
    """Return a runtime session id, auto-selecting when ``session_id`` is omitted."""
    session_store = store or SessionStore()
    if session_id is not None:
        session_store.get_session(session_id)
        return session_id
    return session_store.get_unique_running_session()["session_id"]


def resolve_running_session_id(
    session_id: str | None = None,
    *,
    store: SessionStore | None = None,
) -> str:
    """Return a running session id, auto-selecting when ``session_id`` is omitted."""
    session_store = store or SessionStore()
    if session_id is not None:
        meta = session_store.get_session(session_id)
        if meta.get("status") != "running":
            raise ValueError(f"Session '{session_id}' is not running.")
        return session_id
    return session_store.get_unique_running_session()["session_id"]
