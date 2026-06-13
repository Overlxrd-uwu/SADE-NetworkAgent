"""Load a session document and its failure injection records."""

from __future__ import annotations

from nika.utils.session_resolve import resolve_session_id
from nika.utils.session_store import SessionStore


def inspect_session(session_id: str | None = None) -> tuple[dict, list[dict]]:
    """Return session metadata and failure injection records."""
    store = SessionStore()
    resolved_id = resolve_session_id(session_id, store=store)
    data = store.get_session(resolved_id)
    injections = list(data.pop("failure_injections", []))
    return data, injections
