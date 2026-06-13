"""Shared CLI formatting utilities."""

from datetime import datetime, timezone

import typer

from nika.utils.session_resolve import resolve_running_session_id, resolve_session_id


def env_id_from_lab(lab_name: str | None) -> str:
    """Derive a short display ENV ID from a lab instance name.

    Lab names follow the pattern ``{scenario}__{MMDDHHMMSS}-{6hex}``.
    We extract the trailing hex token so the ID is stable and short.
    """
    if not lab_name:
        return "—"
    parts = lab_name.rsplit("__", 1)
    if len(parts) == 2:
        hex_part = parts[1].rsplit("-", 1)[-1][:6]
        return f"env_{hex_part}"
    return f"env_{lab_name[:6]}"


def human_age(iso_str: str | None) -> str:
    """Return a compact human-readable duration since *iso_str*."""
    if not iso_str:
        return "—"
    try:
        then = datetime.fromisoformat(iso_str)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        total = int((datetime.now(timezone.utc) - then).total_seconds())
        if total < 60:
            return f"{total}s"
        if total < 3600:
            return f"{total // 60}m"
        if total < 86400:
            h, rem = divmod(total, 3600)
            return f"{h}h{rem // 60}m"
        d, rem = divmod(total, 86400)
        return f"{d}d{rem // 3600}h"
    except Exception:
        return "—"


def fmt_table(headers: list[str], rows: list[list[str]]) -> str:
    """Return an aligned ASCII table string (no borders)."""
    if not rows:
        widths = [len(h) for h in headers]
    else:
        widths = [
            max(len(h), max(len(r[i]) for r in rows))
            for i, h in enumerate(headers)
        ]
    sep = "  ".join("-" * w for w in widths)
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    data_lines = ["  ".join(c.ljust(w) for c, w in zip(row, widths)) for row in rows]
    return "\n".join([header_line, sep] + data_lines)


def require_session_id(session_id: str | None = None) -> str:
    """Resolve a runtime session id or raise ``typer.BadParameter``."""
    try:
        return resolve_session_id(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def require_running_session_id(session_id: str | None = None) -> str:
    """Resolve a running session id or raise ``typer.BadParameter``."""
    try:
        return resolve_running_session_id(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
