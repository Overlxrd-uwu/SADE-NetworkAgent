"""Benchmark runner: full pipeline from env to evaluation."""

from pathlib import Path

import typer

from nika.net_env.net_env_pool import scenario_requires_topo_tier
from nika.workflows.benchmark.run import (
    default_benchmark_csv_path,
    run_benchmark_from_csv,
    run_single_benchmark,
)

benchmark_app = typer.Typer(help="Run curated benchmark cases (env → fault → agent → eval).")


@benchmark_app.command("run")
def benchmark_run(
    scenario: str | None = typer.Argument(
        default=None,
        metavar="SCENARIO",
        help="Scenario id for a single case (omit for CSV batch mode).",
    ),
    csv: Path | None = typer.Option(
        None,
        "--csv",
        help="Benchmark CSV path (batch mode). Defaults to benchmark/benchmark_selected.csv under the repo root.",
    ),
    problem: str | None = typer.Option(
        None,
        "--problem",
        help="Problem id for a single case (required with SCENARIO).",
    ),
    tier: str | None = typer.Option(
        None,
        "-t",
        "--tier",
        help="Topology tier s, m, or l (required only for scalable scenarios).",
    ),
    agent_type: str = typer.Option("react", "-a", "--agent", help="Agent implementation."),
    llm_backend: str = typer.Option("openai", "-b", "--backend", help="LLM provider (openai, ollama, deepseek)."),
    model: str = typer.Option("gpt-5-mini", "-m", "--model", help="Model id for the agent."),
    max_steps: int = typer.Option(20, "-n", "--max-steps", help="Max agent steps."),
    parallel: int = typer.Option(
        1,
        "-j",
        "--parallel",
        help="Number of benchmark cases to run concurrently in CSV batch mode (default: 1).",
    ),
    run_judge: bool = typer.Option(
        False,
        "--judge",
        help="Run LLM-as-judge after metrics (default: metrics and publish only).",
    ),
    judge_backend: str | None = typer.Option(
        None,
        "--judge-backend",
        help="LLM provider for the judge (required with --judge).",
    ),
    judge_model: str | None = typer.Option(
        None,
        "--judge-model",
        help="Model id for the judge (required with --judge).",
    ),
) -> None:
    """Run one benchmark row from CSV, or a single case when SCENARIO and --problem are set."""
    if run_judge:
        if not judge_backend or not judge_model:
            raise typer.BadParameter("--judge-backend and --judge-model are required when --judge is set.")
    elif judge_backend is not None or judge_model is not None:
        raise typer.BadParameter("Pass --judge to enable LLM judge; omit --judge-backend/--judge-model otherwise.")

    if scenario is not None and csv is not None:
        raise typer.BadParameter("Use either SCENARIO (single-case mode) or --csv (batch mode), not both.")

    single_mode = scenario is not None

    if single_mode:
        if parallel != 1:
            raise typer.BadParameter("--parallel applies to CSV batch mode only; omit it for a single case.")
        if not problem:
            raise typer.BadParameter("--problem is required when SCENARIO is given.")
        if scenario_requires_topo_tier(scenario) and not tier:
            raise typer.BadParameter(f"Scenario '{scenario}' requires -t/--tier (s, m, or l).")
        if not scenario_requires_topo_tier(scenario) and tier is not None:
            raise typer.BadParameter(f"Scenario '{scenario}' does not use tiers; omit -t/--tier.")
        topo = tier or ""
        run_single_benchmark(
            problem=problem,
            scenario=scenario,
            topo_size=topo,
            agent_type=agent_type,
            llm_backend=llm_backend,
            model=model,
            max_steps=max_steps,
            run_judge=run_judge,
            judge_llm_backend=judge_backend,
            judge_model=judge_model,
        )
        return

    if problem is not None:
        raise typer.BadParameter("--problem without SCENARIO is invalid; pass SCENARIO or use batch mode with --csv.")

    benchmark_path = str(csv) if csv is not None else default_benchmark_csv_path()
    run_benchmark_from_csv(
        benchmark_file=benchmark_path,
        agent_type=agent_type,
        llm_backend=llm_backend,
        model=model,
        max_steps=max_steps,
        parallel=parallel,
        run_judge=run_judge,
        judge_llm_backend=judge_backend,
        judge_model=judge_model,
    )
