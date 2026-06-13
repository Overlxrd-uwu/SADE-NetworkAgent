"""Commands for offline evaluation (metrics, judge, publish, summary)."""

import typer

eval_app = typer.Typer(help="Evaluate a completed agent session.")


@eval_app.command("metrics")
def eval_metrics(
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Compute rule-based scores and trace stats on a closed session; write eval_metrics.json."""
    from nika.workflows.eval.session import run_eval_metrics

    try:
        run_eval_metrics(session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@eval_app.command("judge")
def eval_judge(
    judge_backend: str = typer.Option(
        ...,
        "-b",
        "--backend",
        help="LLM provider for the judge (openai, ollama, deepseek).",
    ),
    judge_model: str = typer.Option(..., "-m", "--model", help="Judge model id."),
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Run LLM-as-judge on a closed session; write llm_judge.json."""
    from nika.workflows.eval.session import run_llm_judge

    try:
        run_llm_judge(judge_backend, judge_model, session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@eval_app.command("publish")
def eval_publish(
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Validate eval artifacts on a closed session and record publish completion."""
    from nika.workflows.eval.session import publish_session_eval

    try:
        publish_session_eval(session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@eval_app.command("summary")
def eval_summary(
    output: str | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output CSV path (default: results/0_summary/evaluation_summary.csv).",
    ),
    problem: list[str] | None = typer.Option(
        None,
        "-p",
        "--problem",
        help="Include only sessions with this root-cause / problem id (repeatable).",
    ),
    env: list[str] | None = typer.Option(
        None,
        "-e",
        "--env",
        help="Include only sessions from this scenario / net env (repeatable).",
    ),
    category: list[str] | None = typer.Option(
        None,
        "-c",
        "--category",
        help="Include only sessions in this root-cause category (repeatable).",
    ),
    session_id: list[str] | None = typer.Option(
        None,
        "--session-id",
        help="Include only these session ids (repeatable).",
    ),
    agent: list[str] | None = typer.Option(
        None,
        "-a",
        "--agent",
        help="Include only sessions run with this agent type (repeatable).",
    ),
    model: list[str] | None = typer.Option(
        None,
        "--model",
        help="Include only sessions run with this model id (repeatable).",
    ),
) -> None:
    """Aggregate finished sessions under results/ into one CSV file."""
    from nika.workflows.eval.summary import run_eval_summary

    try:
        out_path = run_eval_summary(
            output_path=output,
            problems=problem,
            envs=env,
            categories=category,
            session_ids=session_id,
            agent_types=agent,
            models=model,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Wrote summary CSV: {out_path}")


@eval_app.command("clean")
def eval_clean(
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirmation prompt."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Delete session files even when running sessions exist.",
    ),
) -> None:
    """Delete historical results under results/ and runtime session JSON files."""
    from nika.config import RESULTS_DIR, SESSIONS_DIR
    from nika.utils.session_store import SessionStore
    from nika.workflows.eval.clean import run_eval_clean

    running = SessionStore().list_running_sessions()
    if running and not force:
        ids = ", ".join(str(row.get("session_id", "?")) for row in running)
        raise typer.BadParameter(
            f"{len(running)} running session(s) found ({ids}). "
            "Close them with `nika session close` first, or pass --force."
        )

    label = f"all files under {RESULTS_DIR} and session files under {SESSIONS_DIR}"
    if running and force:
        label += f" (including {len(running)} running session file(s))"
    if not yes:
        confirmed = typer.confirm(f"Delete {label}?", default=False)
        if not confirmed:
            raise typer.Abort()

    try:
        report = run_eval_clean(force=force)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"Removed {report.results_entries_removed} entr{'y' if report.results_entries_removed == 1 else 'ies'} "
        f"under {RESULTS_DIR} and {report.session_files_removed} session file(s) under {SESSIONS_DIR}."
    )
