"""Remove persisted evaluation artifacts and runtime session documents."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from nika.config import RESULTS_DIR, SESSIONS_DIR
from nika.utils.session_store import SessionStore


@dataclass(frozen=True)
class EvalCleanReport:
    session_files_removed: int
    results_entries_removed: int


def remove_session_results(
    session_id: str,
    *,
    results_dir: str | Path | None = None,
) -> bool:
    """Remove ``results/{session_id}/`` if it exists."""
    session_results = Path(results_dir or RESULTS_DIR) / session_id
    if not session_results.exists():
        return False
    shutil.rmtree(session_results)
    return True


def run_eval_clean(
    *,
    results_dir: str | Path | None = None,
    sessions_dir: str | Path | None = None,
    force: bool = False,
) -> EvalCleanReport:
    """Delete all contents under ``results/`` and all session JSON files."""
    results_root = Path(results_dir or RESULTS_DIR)
    sessions_root = Path(sessions_dir or SESSIONS_DIR)

    running = SessionStore(sessions_root).list_running_sessions()
    if running and not force:
        ids = ", ".join(str(row.get("session_id", "?")) for row in running)
        raise ValueError(
            f"{len(running)} running session(s) found ({ids}). "
            "Close them with `nika session close` first, or pass --force."
        )

    session_files_removed = 0
    if sessions_root.exists():
        for path in sessions_root.glob("*.json"):
            path.unlink()
            session_files_removed += 1

    results_entries_removed = 0
    if results_root.exists():
        for path in results_root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            results_entries_removed += 1

    return EvalCleanReport(
        session_files_removed=session_files_removed,
        results_entries_removed=results_entries_removed,
    )
