"""Batch or single-case benchmark runs (env → inject → agent → eval)."""

from __future__ import annotations

import csv
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from nika.config import BENCHMARK_DIR, RESULTS_DIR
from nika.net_env.net_env_pool import scenario_requires_topo_tier
from nika.workflows.agent.run import start_agent
from nika.workflows.env.start import start_net_env
from nika.workflows.eval.session import eval_results
from nika.workflows.failure.inject import inject_failure

_BENCHMARK_DONE_PREFIX = "benchmark_done "


def default_benchmark_csv_path() -> str:
    return str(BENCHMARK_DIR / "benchmark_selected.csv")


def _benchmark_row_cli_args(
    row: dict,
    *,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    run_judge: bool,
    judge_llm_backend: str | None,
    judge_model: str | None,
) -> list[str]:
    args = [
        row["scenario"],
        "--problem",
        row["problem"],
        "-a",
        agent_type,
        "-b",
        llm_backend,
        "-m",
        model,
        "-n",
        str(max_steps),
    ]
    topo = row.get("topo_size") or ""
    if topo:
        args += ["-t", topo]
    if run_judge:
        args += ["--judge", "--judge-backend", judge_llm_backend, "--judge-model", judge_model]
    return args


def _run_benchmark_row_subprocess(
    row: dict,
    *,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    run_judge: bool,
    judge_llm_backend: str | None,
    judge_model: str | None,
) -> None:
    """Run one CSV row via a subprocess for thread-safe parallel batch execution."""
    cli_args = _benchmark_row_cli_args(
        row,
        agent_type=agent_type,
        llm_backend=llm_backend,
        model=model,
        max_steps=max_steps,
        run_judge=run_judge,
        judge_llm_backend=judge_llm_backend,
        judge_model=judge_model,
    )
    proc = subprocess.run(
        [sys.executable, "-m", "nika.cli.main", "benchmark", "run", *cli_args],
        capture_output=True,
        text=True,
    )
    output = proc.stdout
    if proc.stderr:
        output += proc.stderr
    if proc.returncode != 0:
        scenario = row.get("scenario", "?")
        problem = row.get("problem", "?")
        raise RuntimeError(
            f"[{scenario}/{problem}] `nika benchmark run {' '.join(cli_args)}` "
            f"exited {proc.returncode}:\n{output}"
        )
    if output:
        print(output, end="" if output.endswith("\n") else "\n")


def run_single_benchmark(
    problem: str,
    scenario: str,
    topo_size: str,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    *,
    run_judge: bool = False,
    judge_llm_backend: str | None = None,
    judge_model: str | None = None,
) -> str:
    """
    Run a single benchmark case.

    Returns:
        The session id for the completed run.
    """
    print(f"Running benchmark for Problem: {problem}, Scenario: {scenario}, Topo Size: {topo_size}")

    tier = topo_size if topo_size else None
    if scenario_requires_topo_tier(scenario) and not tier:
        raise ValueError(f"Scenario '{scenario}' requires a non-empty topology tier (-t s|m|l).")
    if not scenario_requires_topo_tier(scenario):
        tier = None

    session_id = start_net_env(scenario, tier, redeploy=True)
    session_dir = Path(RESULTS_DIR) / session_id

    inject_failure(problem_names=[problem], session_id=session_id)

    start_agent(
        agent_type=agent_type,
        llm_backend=llm_backend,
        model=model,
        max_steps=max_steps,
        session_id=session_id,
    )

    eval_results(
        session_id=session_id,
        run_judge=run_judge,
        judge_llm_backend=judge_llm_backend,
        judge_model=judge_model,
    )

    print(
        f"{_BENCHMARK_DONE_PREFIX}session_id={session_id} scenario={scenario} "
        f"problem={problem} session_dir={session_dir}"
    )
    return session_id


def run_benchmark_from_csv(
    benchmark_file: str,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    *,
    parallel: int = 1,
    run_judge: bool = False,
    judge_llm_backend: str | None = None,
    judge_model: str | None = None,
) -> None:
    """
    Run benchmark cases defined in a CSV file.

    The CSV file must contain the following columns:
    - problem
    - scenario
    - topo_size (same values as ``nika env run -t``: s, m, l, or empty)
    """
    if parallel < 1:
        raise ValueError("parallel must be >= 1")

    with open(benchmark_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"No benchmark rows found in {benchmark_file}")
        return

    if parallel == 1:
        for row in rows:
            run_single_benchmark(
                problem=row["problem"],
                scenario=row["scenario"],
                topo_size=row.get("topo_size") or "",
                agent_type=agent_type,
                llm_backend=llm_backend,
                model=model,
                max_steps=max_steps,
                run_judge=run_judge,
                judge_llm_backend=judge_llm_backend,
                judge_model=judge_model,
            )
        return

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = [
            pool.submit(
                _run_benchmark_row_subprocess,
                row,
                agent_type=agent_type,
                llm_backend=llm_backend,
                model=model,
                max_steps=max_steps,
                run_judge=run_judge,
                judge_llm_backend=judge_llm_backend,
                judge_model=judge_model,
            )
            for row in rows
        ]
        for future in as_completed(futures):
            future.result()
