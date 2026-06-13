"""Resolve lab and result paths for MCP tools from ``NIKA_SESSION_ID``.

``NIKA_SESSION_ID`` is injected into each MCP subprocess by ``MCPServerConfig``
when the agent loads tools; it is not written to the parent agent process env.
Lab name, result directory, and related metadata are loaded from
``SessionStore`` at tool invocation time.
"""

from __future__ import annotations

import os
from typing import Any

from nika.config import RESULTS_DIR
from nika.utils.session_store import SessionStore

SESSION_ID_ENV = "NIKA_SESSION_ID"


def require_session_id() -> str:
    session_id = os.getenv(SESSION_ID_ENV)
    if not session_id:
        raise ValueError(
            f"{SESSION_ID_ENV} is not set. MCP tools must be started with a bound session id."
        )
    return session_id


def get_session_meta() -> dict[str, Any]:
    session_id = require_session_id()
    meta = SessionStore().get_session(session_id)
    if meta.get("status") != "running":
        raise ValueError(f"Session '{session_id}' is not running.")
    return meta


def get_lab_name() -> str:
    meta = get_session_meta()
    lab_name = meta.get("lab_name") or (meta.get("scenario_params") or {}).get("lab_name")
    if not lab_name:
        raise ValueError(f"Session '{meta.get('session_id')}' has no lab_name.")
    return str(lab_name)


def get_session_dir() -> str:
    meta = get_session_meta()
    session_dir = meta.get("session_dir")
    if session_dir:
        return str(session_dir)
    session_id = str(meta["session_id"])
    return f"{RESULTS_DIR}/{session_id}"
