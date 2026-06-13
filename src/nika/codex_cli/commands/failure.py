"""Commands for fault injection."""

import json

import typer

from nika.codex_cli.utils import require_running_session_id

failure_app = typer.Typer(help="Inject faults into the running lab.")


def _parse_set_options(raw_items: list[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw in raw_items or []:
        if "=" not in raw:
            raise typer.BadParameter(f"Invalid --set value {raw!r}. Use key=value.")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"Invalid --set value {raw!r}. Key cannot be empty.")
        overrides[key] = value.strip()
    return overrides


@failure_app.command("list")
def failure_list() -> None:
    """Print injectable problem ids."""
    from nika.orchestrator.problems.prob_pool import list_avail_problem_names

    for name in sorted(list_avail_problem_names()):
        typer.echo(name)


@failure_app.command("inject")
def failure_inject(
    problems: list[str] = typer.Argument(
        ...,
        metavar="PROBLEM",
        help="One or more problem ids (see `nika failure list`).",
    ),
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
    sets: list[str] | None = typer.Option(
        None,
        "--set",
        help="Override injection parameters as key=value. Repeat the flag for multiple values.",
    ),
) -> None:
    """Inject one or more faults for the current session."""
    from nika.workflows.failure.inject import inject_failure

    if not problems:
        raise typer.BadParameter("Provide at least one problem name.")
    overrides = _parse_set_options(sets)
    try:
        inject_failure(problems, session_id=session_id, param_overrides=overrides)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@failure_app.command("describe")
def failure_describe(
    problem: str = typer.Argument(..., metavar="PROBLEM", help="Problem id to inspect."),
) -> None:
    """Describe supported parameters for one failure type."""
    from nika.orchestrator.problems.prob_pool import get_problem_class
    from nika.orchestrator.problems.problem_base import TaskLevel
    from nika.utils.failure_params import get_failure_param_schema

    cls = get_problem_class(problem, TaskLevel.DETECTION)
    if cls is None:
        typer.echo(f"Unknown problem: {problem}", err=True)
        raise typer.Exit(1)

    ParamsClass = getattr(cls, "Params", None)
    if ParamsClass is not None:
        schema = ParamsClass.model_json_schema()
        typer.echo(f"Problem: {problem}")
        if schema.get("description"):
            typer.echo(schema["description"])
        typer.echo("\nParameter schema (JSON Schema):")
        typer.echo(json.dumps(schema, indent=2))
        params_hint = " ".join(f"--set {name}=<value>" for name in schema.get("properties", {}))
        typer.echo(f"\nUsage example:\n  nika failure inject {problem} {params_hint}")
        return

    # Legacy path for failures that still use FailureParamSchema.
    legacy_schema = get_failure_param_schema(problem)
    if legacy_schema is None:
        typer.echo(f"{problem}: no typed parameter schema yet.")
        typer.echo("You can still run injection without --set; defaults come from scenario runtime.")
        return

    typer.echo(f"{legacy_schema.problem_name}: {legacy_schema.summary}")
    typer.echo("Parameters:")
    for field in legacy_schema.fields:
        default_text = f"default={field.default!r}" if field.default is not None else "default=<runtime>"
        required_text = "required" if field.required else "optional"
        typer.echo(f"- {field.name} ({field.param_type}, {required_text}, {default_text}) - {field.description}")
    typer.echo(f"Example:\n  {legacy_schema.example}")


@failure_app.command("ps")
def failure_ps(
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """List persisted failure injection states for one session."""
    from nika.utils.session_store import SessionStore

    target_session_id = require_running_session_id(session_id)
    rows = SessionStore().list_failure_injections(session_id=target_session_id)
    if not rows:
        typer.echo(f"No failure records for session {target_session_id}.")
        return

    for item in rows:
        typer.echo(
            " | ".join(
                [
                    f"id={item.get('id')}",
                    f"session_id={item.get('session_id')}",
                    f"problem={item.get('problem_name')}",
                    f"status={item.get('status')}",
                    f"start={item.get('start_time')}",
                    f"end={item.get('end_time')}",
                    f"params={item.get('injection_params')}",
                ]
            )
        )
