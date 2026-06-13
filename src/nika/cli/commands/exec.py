"""Execute shell commands inside a host container in the running lab."""

from typing import Optional

import typer

def _exec_in_host(*, host: str, command: str, session_id: str | None, timeout: float) -> str:
    from nika.workflows.exec.command import exec_command_in_host

    return exec_command_in_host(host=host, command=command, session_id=session_id, timeout=timeout)


def _exit_with_message(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=2)


def exec_command(
    host: str = typer.Argument(..., metavar="HOST", help="Target host/container name in the selected lab."),
    command_parts: list[str] = typer.Argument(..., metavar="COMMAND", help="Shell command to execute inside HOST."),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
    timeout: float = typer.Option(10.0, "--timeout", help="Execution timeout in seconds (default: 10)."),
) -> None:
    """Execute COMMAND inside HOST for one session-bound lab."""
    if timeout <= 0:
        _exit_with_message("--timeout must be greater than 0.")
    command = " ".join(command_parts).strip()
    if command == "":
        _exit_with_message("COMMAND cannot be empty.")

    try:
        output = _exec_in_host(host=host, command=command, session_id=session_id, timeout=timeout)
    except (FileNotFoundError, ValueError) as exc:
        _exit_with_message(str(exc))
    typer.echo(output)
