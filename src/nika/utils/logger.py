"""System logger: writes human-readable lines to runtime/nika.log (global)
and structured JSONL events to {session_dir}/events.jsonl once a session
directory is bound via ``bind_session_dir()``.

Usage
-----
Basic logging (existing callers unchanged):
    from nika.utils.logger import system_logger
    system_logger.info("some message")

Structured event logging (new, extensible):
    from nika.utils.logger import log_event
    log_event("env_start", "Lab deployed", scenario="simple_bgp", session_id="...")
    log_event("failure_inject_error", "Inject failed", error="timeout", problem="link_down")

Bind a session directory (call once session_dir is known):
    from nika.utils.logger import bind_session_dir
    bind_session_dir("/path/to/results/link_down/20260608-153412-ab3c1f")
"""

import json
import logging
import os
from datetime import datetime

from nika.config import BASE_DIR

_LOG_PATH = os.path.join(BASE_DIR, "runtime", "nika.log")
_session_events_path: str | None = None


def _ensure_log_dir() -> None:
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)


class _JsonlHandler(logging.Handler):
    """Appends a structured JSON line to events.jsonl."""

    def __init__(self, events_path: str) -> None:
        super().__init__()
        self._path = events_path

    def emit(self, record: logging.LogRecord) -> None:
        entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event_type", "system"),
            "message": record.getMessage(),
        }
        extra = getattr(record, "data", None)
        if extra:
            entry["data"] = extra
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            self.handleError(record)


def _build_logger() -> logging.Logger:
    _ensure_log_dir()
    logger = logging.getLogger("SystemLogger")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        fh = logging.FileHandler(_LOG_PATH, encoding="utf-8", mode="a")
        fh.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)
    elif not os.path.exists(_LOG_PATH):
        for h in list(logger.handlers):
            if isinstance(h, logging.FileHandler):
                logger.removeHandler(h)
        fh = logging.FileHandler(_LOG_PATH, encoding="utf-8", mode="a")
        fh.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)
    return logger


system_logger = _build_logger()


def refresh_logger() -> logging.Logger:
    """Re-attach the file handler (useful when log file rotates between commands)."""
    global system_logger
    logger = logging.getLogger("SystemLogger")
    for h in list(logger.handlers):
        logger.removeHandler(h)
    system_logger = _build_logger()
    if _session_events_path:
        _attach_jsonl_handler(_session_events_path)
    return system_logger


def bind_session_dir(session_dir: str) -> None:
    """Attach a per-session JSONL handler; call once session_dir is known."""
    global _session_events_path
    os.makedirs(session_dir, exist_ok=True)
    _session_events_path = os.path.join(session_dir, "events.jsonl")
    _attach_jsonl_handler(_session_events_path)


def _attach_jsonl_handler(events_path: str) -> None:
    logger = logging.getLogger("SystemLogger")
    for h in list(logger.handlers):
        if isinstance(h, _JsonlHandler):
            logger.removeHandler(h)
    logger.addHandler(_JsonlHandler(events_path))


def log_event(event_type: str, message: str, **data) -> None:
    """Log a structured event with optional key/value metadata.

    Writes a human-readable line to nika.log and, when a session dir is
    bound, a structured JSON line to events.jsonl.

    Example::
        log_event("env_start", "Lab deployed", scenario="simple_bgp", session_id="...")
        log_event("failure_inject_error", "Inject failed", error="timeout")
    """
    system_logger.info(message, extra={"event_type": event_type, "data": data or None})
