"""Commands for deploying and listing network environments."""

import typer

from nika.codex_cli.utils import env_id_from_lab, fmt_table, human_age

env_app = typer.Typer(help="Kathara lab scenarios.")


@env_app.command("list")
def env_list() -> None:
    """Print scenario ids registered in the net env pool."""
    from nika.net_env.net_env_pool import list_all_net_envs

    for name in sorted(list_all_net_envs()):
        typer.echo(name)


@env_app.command("run")
def env_run(
    name: str = typer.Argument(..., metavar="NAME", help="Scenario id (see `nika env list`)."),
    tier: str | None = typer.Option(
        None,
        "-t",
        "--tier",
        help="Topology tier s, m, or l (required only for scalable scenarios).",
    ),
    no_redeploy: bool = typer.Option(False, "--no-redeploy", help="If set, do not redeploy when the lab already exists."),
    instance_tag: str | None = typer.Option(
        None,
        "--instance-tag",
        help="Optional tag for lab instance naming; required for human-friendly concurrent runs.",
    ),
) -> None:
    """Deploy one scenario and start a new session."""
    from nika.workflows.env.start import start_net_env

    session_id = start_net_env(name, tier, redeploy=not no_redeploy, instance_tag=instance_tag)
    typer.echo(f"session_id={session_id}")


@env_app.command("ps")
def env_ps() -> None:
    """List running env instances, one row per deployed lab.

    Sessions are grouped by their lab instance so you can see at a glance
    how many sessions are active for each environment and how long it has
    been running.

    \b
    Columns
    -------
    ENV ID      short ID derived from the deployed lab instance
    TOPOLOGY    scenario name, with tier appended when applicable (e.g. dc_clos_bgp/m)
    STATUS      running | finished
    AGE         time elapsed since the env was created
    SESSIONS    number of active sessions bound to this env
    ENDPOINT    service endpoint when available, — otherwise
    """
    from nika.utils.session_store import SessionStore

    sessions = SessionStore().list_running_sessions()
    if not sessions:
        typer.echo("No running env instances.")
        return

    # Deduplicate by lab_name — one env row per distinct deployed lab.
    seen_labs: set[str] = set()
    headers = ["ENV ID", "TOPOLOGY", "STATUS", "AGE", "SESSIONS", "ENDPOINT"]
    rows: list[list[str]] = []

    for item in sessions:
        lab_name: str = item.get("lab_name") or ""
        if lab_name in seen_labs:
            continue
        seen_labs.add(lab_name)

        env_id = env_id_from_lab(lab_name)

        scenario = item.get("scenario_name", "—")
        tier = item.get("scenario_topo_size")
        topology = f"{scenario}/{tier}" if tier else scenario

        status = item.get("status", "—")
        age = human_age(item.get("created_at"))

        # Count all running sessions sharing this lab instance.
        active = sum(
            1 for s in sessions
            if s.get("lab_name") == lab_name and s.get("status") == "running"
        )
        sessions_col = f"{active} active"

        endpoint = item.get("endpoint", "—")

        rows.append([env_id, topology, status, age, sessions_col, endpoint])

    typer.echo(fmt_table(headers, rows))
