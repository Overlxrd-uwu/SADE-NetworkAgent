"""List runtime session documents."""

from __future__ import annotations

import json

from nika.config import SESSIONS_DIR
from nika.utils.session_store import SessionStore


def list_sessions(*, running_only: bool = True) -> list[dict]:
    """Return session documents, newest first."""
    if running_only:
        return SessionStore().list_running_sessions()

    sessions_dir = SESSIONS_DIR
    result: list[dict] = []
    if not sessions_dir.exists():
        return result
    for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            result.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result
