"""Commands for offline evaluation (metrics, judge, publish, summary)."""

import typer

eval_app = typer.Typer(help="Evaluate a completed agent session.")


@eval_app.command("metrics")
def eval_metrics(
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Compute rule-based scores and trace stats; write eval_metrics.json."""
    from nika.workflows.session_eval import run_eval_metrics

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
    """Run LLM-as-judge only; write llm_judge.json."""
    from nika.workflows.session_eval import run_llm_judge

    try:
        run_llm_judge(judge_backend, judge_model, session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@eval_app.command("publish")
def eval_publish(
    no_destroy: bool = typer.Option(
        False,
        "--no-destroy",
        help="Leave the Kathara lab running after finishing the session.",
    ),
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Finalize run.json, optionally undeploy, and clear the runtime session."""
    from nika.workflows.session_eval import publish_session_eval

    try:
        publish_session_eval(destroy_env=not no_destroy, session_id=session_id)
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
    from nika.workflows.eval_summary import run_eval_summary

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
