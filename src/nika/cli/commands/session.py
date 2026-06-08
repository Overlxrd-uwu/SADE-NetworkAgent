"""Commands for inspecting and managing active sessions."""

import json

import typer

from nika.cli.utils import env_id_from_lab, fmt_table, human_age

session_app = typer.Typer(help="Active session management.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent_summary(session: dict) -> str:
    """Summarise agent activity stored in a session document."""
    agent_type = session.get("agent_type")
    if not agent_type:
        return "—"
    start = session.get("start_time")
    end = session.get("end_time")
    if start and not end:
        return f"1 running ({agent_type})"
    if start and end:
        return f"1 done ({agent_type})"
    return "—"


def _load_all_sessions() -> list[dict]:
    """Return all session documents (running + finished) sorted newest-first."""
    import json as _json
    from pathlib import Path

    from nika.config import BASE_DIR

    sessions_dir = Path(BASE_DIR) / "runtime" / "sessions"
    result = []
    if not sessions_dir.exists():
        return result
    for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            result.append(_json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@session_app.command("ps")
def session_ps(
    all_sessions: bool = typer.Option(False, "--all", "-a", help="Include finished sessions."),
) -> None:
    """List sessions and their runtime status.

    By default only running sessions are shown. Pass --all to include
    finished ones.

    \b
    Columns
    -------
    SESSION ID  unique session identifier
    ENV ID      short ID derived from the deployed lab instance
    NAME        scenario name (topology)
    STATUS      running | finished
    FAILURES    number of injected failure records
    AGENTS      agent activity summary
    """
    from nika.utils.session_store import SessionStore

    if all_sessions:
        sessions = _load_all_sessions()
    else:
        sessions = SessionStore().list_running_sessions()

    if not sessions:
        typer.echo("No sessions found.")
        return

    headers = ["SESSION ID", "ENV ID", "NAME", "STATUS", "FAILURES", "AGENTS"]
    rows: list[list[str]] = []
    for s in sessions:
        n_failures = len(s.get("failure_injections", []))
        rows.append([
            s.get("session_id", "—"),
            env_id_from_lab(s.get("lab_name")),
            s.get("scenario_name", "—"),
            s.get("status", "—"),
            str(n_failures),
            _agent_summary(s),
        ])

    typer.echo(fmt_table(headers, rows))


@session_app.command("inspect")
def session_inspect(
    session_id: str | None = typer.Argument(None, help="Session ID. Auto-selects when only one is running."),
) -> None:
    """Show detailed information about a session.

    Prints the full session document as formatted JSON, with failure
    injection records summarised below the main body.
    """
    from nika.utils.session_store import SessionStore

    store = SessionStore()
    try:
        data = store.get_session(session_id) if session_id else store.get_unique_running_session()
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    injections: list[dict] = data.pop("failure_injections", [])

    # Main session metadata
    typer.echo(json.dumps(data, indent=2, default=str))

    # Failure injections summary
    if injections:
        typer.echo(f"\nfailure_injections  ({len(injections)} record{'s' if len(injections) != 1 else ''}):")
        hdr = ["IDX", "PROBLEM", "STATUS", "PARAMS"]
        fi_rows: list[list[str]] = []
        for i, inj in enumerate(injections):
            params_raw = inj.get("injection_params", {})
            params_str = json.dumps(params_raw, default=str)
            if len(params_str) > 60:
                params_str = params_str[:57] + "..."
            fi_rows.append([
                str(i),
                inj.get("problem_name", "—"),
                inj.get("status", "—"),
                params_str,
            ])
        for line in fmt_table(hdr, fi_rows).splitlines():
            typer.echo("  " + line)
    else:
        typer.echo("\nfailure_injections  (none)")


@session_app.command("close")
def session_close(
    session_id: str | None = typer.Argument(None, help="Session ID, or 'all' to close every running session."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Close one or all sessions: stop containers and clean up runtime state.

    Pass a SESSION_ID to close a specific session, or the literal word
    ``all`` to close every running session at once.  When SESSION_ID is
    omitted and only one session is running it is selected automatically.

    The Kathará lab is undeployed, all failure records are marked ended,
    and the runtime session file is removed.
    """
    from nika.workflows.net_env_stop import stop_net_env
    from nika.utils.session_store import SessionStore

    close_all = session_id is not None and session_id.lower() == "all"

    if close_all:
        running = SessionStore().list_running_sessions()
        if not running:
            typer.echo("No running sessions.")
            return
        label = f"all {len(running)} running session(s)"
        if not yes:
            confirmed = typer.confirm(f"Stop lab containers and clear {label}?", default=False)
            if not confirmed:
                raise typer.Abort()
        try:
            stop_net_env(stop_all=True)
        except (FileNotFoundError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Closed: {label}")
        return

    label = session_id if session_id else "the active session"
    if not yes:
        confirmed = typer.confirm(
            f"Stop lab containers and clear {label}?",
            default=False,
        )
        if not confirmed:
            raise typer.Abort()

    try:
        stop_net_env(session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Closed: {label}")
