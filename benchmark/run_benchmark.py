import argparse
import csv
import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime

from nika.config import BASE_DIR, RESULTS_DIR
from nika.net_env.net_env_pool import get_net_env_instance
from nika.evaluator.result_log import EvalResult, record_eval_result
from nika.utils.session import Session
from scripts.step1_net_env_start import start_net_env
from scripts.step2_failure_inject import inject_failure
from scripts.step3_agent_run import start_agent
from scripts.step4_result_eval import eval_results

cur_dir = os.path.dirname(os.path.abspath(__file__))


def _run_command(
    cmd: list[str],
    *,
    description: str,
    input_text: str | None = None,
    timeout: int = 300,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    print(f"[RECOVER] {description}: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip())
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{description} failed: {detail}")
    return result


def _docker_daemon_healthy() -> bool:
    try:
        result = _run_command(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            description="Checking Docker daemon health",
            timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception as exc:
        print(f"[RECOVER WARNING] Could not check Docker daemon health: {exc}")
        return False


def _raise_docker_unhealthy(context: str) -> None:
    raise RuntimeError(
        f"Docker daemon is unhealthy/stuck during {context}. "
        "Restart Docker Desktop manually and wait until `docker info` succeeds before continuing."
    )


def _has_kathara_containers() -> bool:
    try:
        result = _run_command(
            ["docker", "ps", "-a", "-q", "--filter", "label=kathara"],
            description="Checking for Kathara containers",
            timeout=10,
        )
        return bool(result.stdout.strip())
    except Exception as exc:
        print(f"[RECOVER WARNING] Could not inspect Docker containers: {exc}")
        return True


def _restart_docker_service(docker_service_name: str | None) -> None:
    system_name = platform.system().lower()

    if system_name == "windows":
        candidates = [docker_service_name] if docker_service_name else ["com.docker.service", "docker"]
        names_literal = ", ".join(f"'{name}'" for name in candidates if name)
        ps_script = rf"""
$ErrorActionPreference = "Stop"
$candidates = @({names_literal})
$svc = $null
foreach ($name in $candidates) {{
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($svc) {{ break }}
}}
if (-not $svc) {{
    Write-Output "Docker service not found"
    exit 2
}}
Restart-Service -Name $svc.Name -Force -ErrorAction Stop
Start-Sleep -Seconds 5
$status = (Get-Service -Name $svc.Name).Status
Write-Output ("Restarted " + $svc.Name + " -> " + $status)
if ($status -ne "Running") {{
    exit 3
}}
"""
        _run_command(
            ["powershell", "-NoProfile", "-Command", ps_script],
            description="Restarting Docker service",
            timeout=180,
            check=True,
        )
        return

    service_name = docker_service_name or "docker"
    if shutil.which("systemctl") is None:
        raise RuntimeError("systemctl not found; cannot restart Docker automatically")
    _run_command(
        ["systemctl", "restart", service_name],
        description=f"Restarting Docker service '{service_name}'",
        timeout=180,
        check=True,
    )


def _run_kathara_wipe() -> None:
    kathara_exe = shutil.which("kathara")
    if not kathara_exe:
        raise RuntimeError("Kathara CLI not found in PATH")
    _run_command(
        [kathara_exe, "wipe"],
        description="Running `kathara wipe`",
        input_text="y\n",
        timeout=300,
        check=True,
    )


def _runtime_looks_stale(scenario: str, topo_size) -> bool:
    try:
        net_env = get_net_env_instance(scenario, topo_size=topo_size)
        if net_env.lab_exists():
            return True
    except Exception as exc:
        print(f"[RECOVER WARNING] Could not query lab state for '{scenario}': {exc}")
        return True
    return _has_kathara_containers()


def _cleanup_stale_runtime(
    *,
    scenario: str,
    topo_size,
    docker_service_name: str | None,
    settle_seconds: int,
) -> None:
    print(f"[CLEANUP] Existing runtime detected for scenario '{scenario}'. Cleaning stale state...")

    try:
        net_env = get_net_env_instance(scenario, topo_size=topo_size)
        if net_env.lab_exists():
            print(f"[CLEANUP] Attempting normal undeploy for '{scenario}'")
            net_env.undeploy()
            time.sleep(2)
    except Exception as exc:
        print(f"[CLEANUP WARNING] Normal undeploy did not clear the runtime: {exc}")

    stale_after_undeploy = _runtime_looks_stale(scenario, topo_size)
    if stale_after_undeploy:
        print("[CLEANUP] Escalating to Docker restart + `kathara wipe`.")
        try:
            _restart_docker_service(docker_service_name=docker_service_name)
        except Exception as exc:
            raise RuntimeError(
                "Failed to restart Docker service during cleanup. "
                "On Windows, use an elevated terminal or restart Docker Desktop manually."
            ) from exc
        if not _docker_daemon_healthy():
            _raise_docker_unhealthy("cleanup after Docker restart")
        try:
            _run_kathara_wipe()
        except Exception as exc:
            if not _docker_daemon_healthy():
                _raise_docker_unhealthy("cleanup while running `kathara wipe`")
            raise RuntimeError("`kathara wipe` failed while Docker daemon appeared healthy.") from exc
        if not _docker_daemon_healthy():
            _raise_docker_unhealthy("cleanup after `kathara wipe`")
        if settle_seconds > 0:
            print(f"[CLEANUP] Waiting {settle_seconds}s for runtime to settle...")
            time.sleep(settle_seconds)

    if _runtime_looks_stale(scenario, topo_size):
        raise RuntimeError("Runtime still looks stale after cleanup attempt")

    print("[CLEANUP] Stale runtime cleanup complete.")


def run_single_benchmark(
    problem: str,
    scenario: str,
    topo_size: int,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    judge_llm_backend: str,
    judge_model: str,
    destroy_env: bool,
    auto_recover_stale_env: bool = False,
    docker_service_name: str | None = None,
    recovery_settle_seconds: int = 6,
):
    """
    Run a single benchmark case.

    Args:
        problem: Name of the failure/problem to inject
        scenario: Network scenario name
        topo_size: Topology size
        agent_type: Agent type (e.g., react)
        llm_backend: LLM backend
        model: LLM backend model
        max_steps: Maximum agent steps
        judge_llm_backend: LLM backend used for evaluation
        judge_model: Model used for evaluation
        destroy_env: Whether to destroy the network environment after evaluation
    """

    print(f"Running benchmark for Problem: {problem}, Scenario: {scenario}, Topo Size: {topo_size}")

    # Step 1: Ensure this case starts from a clean runtime state.
    if auto_recover_stale_env and _runtime_looks_stale(scenario, topo_size):
        _cleanup_stale_runtime(
            scenario=scenario,
            topo_size=topo_size,
            docker_service_name=docker_service_name,
            settle_seconds=recovery_settle_seconds,
        )

    # Step 2: Start network environment (always redeploy for single run)
    start_net_env(scenario, topo_size=topo_size, redeploy=True)
    _set_benchmark_scenario_params(topo_size)

    # Step 3: Inject failure
    inject_failure(problem_names=[problem])

    # Step 4: Start agent. Agent-side failures (SDK process death, model error,
    # max-turns without submission) are NOT setup failures — let evaluation
    # still run so the case lands in evaluation_summary.csv as a zero-score
    # row (handled by step4 when no submission file is present), instead of
    # being recorded as a skip in benchmark_skips.csv.
    try:
        start_agent(
            agent_type=agent_type,
            llm_backend=llm_backend,
            model=model,
            max_steps=max_steps,
        )
    except Exception as exc:
        print(
            f"[AGENT-FAIL] Agent run failed for {problem},{scenario},{topo_size}: "
            f"{type(exc).__name__}: {exc}. Continuing to evaluation with no submission."
        )

    # Step 5: Evaluate results
    eval_results(judge_llm_backend=judge_llm_backend, judge_model=judge_model, destroy_env=destroy_env)

    # Step 6: If teardown left stale runtime behind, recover it here.
    if destroy_env and auto_recover_stale_env and _runtime_looks_stale(scenario, topo_size):
        _cleanup_stale_runtime(
            scenario=scenario,
            topo_size=topo_size,
            docker_service_name=docker_service_name,
            settle_seconds=recovery_settle_seconds,
        )


def _set_benchmark_scenario_params(topo_size: str) -> None:
    if topo_size not in {"s", "m", "l"}:
        return

    session = Session()
    session.load_running_session()
    scenario_params = dict(getattr(session, "scenario_params", {}))
    scenario_params.setdefault("topo_size", topo_size)
    session.update_session("scenario_params", scenario_params)


def _problem_metadata(problem: str) -> tuple[str, str]:
    try:
        from nika.orchestrator.problems.prob_pool import list_avail_problem_instances

        problems = list_avail_problem_instances()
        if problem in problems:
            cls = next(iter(problems[problem].values()))
            return cls.META.root_cause_category, cls.META.root_cause_name
    except Exception as exc:
        print(f"[CASE-SKIPPED WARNING] Could not load metadata for {problem!r}: {exc}")
    return "unknown", problem


def _record_skipped_case(
    *,
    problem: str,
    scenario: str,
    topo_size: str,
    agent_type: str,
    model: str,
    reason: Exception,
) -> None:
    root_cause_category, root_cause_name = _problem_metadata(problem)
    session_id = f"SKIP_{datetime.now().strftime('%m%d%H%M%S')}"
    reason_text = f"{type(reason).__name__}: {reason}"
    active_session_id = _active_session_id()
    print(
        f"[CASE-SKIPPED] {problem},{scenario},{topo_size} -> {reason_text}. "
        f"Recorded zero-score row with session_id={session_id}."
    )
    _record_skip_reason(
        problem=problem,
        scenario=scenario,
        topo_size=topo_size,
        agent_type=agent_type,
        model=model,
        skip_session_id=session_id,
        active_session_id=active_session_id,
        reason=reason,
    )

    record_eval_result(
        EvalResult(
            agent_type=agent_type,
            model=model,
            root_cause_category=root_cause_category,
            root_cause_name=root_cause_name,
            net_env=scenario,
            scenario_topo_size=topo_size,
            session_id=session_id,
            in_tokens=0,
            out_tokens=0,
            steps=0,
            tool_calls=0,
            tool_errors=0,
            time_taken=0,
            llm_judge_relevance_score=0,
            llm_judge_correctness_score=0,
            llm_judge_efficiency_score=0,
            llm_judge_clarity_score=0,
            llm_judge_final_outcome_score=0,
            llm_judge_overall_score=0,
            detection_score=0,
            localization_accuracy=0,
            localization_precision=0,
            localization_recall=0,
            localization_f1=0,
            rca_accuracy=0,
            rca_precision=0,
            rca_recall=0,
            rca_f1=0,
        )
    )


def _active_session_id() -> str | None:
    session_path = os.path.join(BASE_DIR, "runtime", "current_session.json")
    if not os.path.exists(session_path):
        return None
    try:
        with open(session_path, encoding="utf-8") as f:
            return json.load(f).get("session_id")
    except Exception:
        return None


def _record_skip_reason(
    *,
    problem: str,
    scenario: str,
    topo_size: str,
    agent_type: str,
    model: str,
    skip_session_id: str,
    active_session_id: str | None,
    reason: Exception,
) -> None:
    log_dir = os.path.join(RESULTS_DIR, "0_summary")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "benchmark_skips.csv")
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent_type": agent_type,
        "model": model,
        "problem": problem,
        "scenario": scenario,
        "topo_size": topo_size,
        "skip_session_id": skip_session_id,
        "active_session_id": active_session_id or "",
        "exception_type": type(reason).__name__,
        "exception_message": str(reason),
    }
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def run_benchmark_from_csv(
    benchmark_file: str,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    judge_llm_backend: str,
    judge_model: str,
    destroy_env: bool,
    auto_recover_stale_env: bool,
    docker_service_name: str | None,
    recovery_settle_seconds: int,
    fail_fast: bool,
):
    """
    Run benchmark cases defined in a CSV file.

    The CSV file must contain the following columns:
    - problem
    - scenario
    - topo_size
    """

    with open(benchmark_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            problem = row["problem"]
            scenario = row["scenario"]
            topo_size = str(row["topo_size"])
            try:
                run_single_benchmark(
                    problem=problem,
                    scenario=scenario,
                    topo_size=topo_size,
                    agent_type=agent_type,
                    llm_backend=llm_backend,
                    model=model,
                    max_steps=max_steps,
                    judge_llm_backend=judge_llm_backend,
                    judge_model=judge_model,
                    destroy_env=destroy_env,
                    auto_recover_stale_env=auto_recover_stale_env,
                    docker_service_name=docker_service_name,
                    recovery_settle_seconds=recovery_settle_seconds,
                )
            except Exception as exc:
                _record_skipped_case(
                    problem=problem,
                    scenario=scenario,
                    topo_size=topo_size,
                    agent_type=agent_type,
                    model=model,
                    reason=exc,
                )
                if auto_recover_stale_env:
                    try:
                        _cleanup_stale_runtime(
                            scenario=scenario,
                            topo_size=topo_size,
                            docker_service_name=docker_service_name,
                            settle_seconds=recovery_settle_seconds,
                        )
                    except Exception as cleanup_exc:
                        print(f"[CASE-SKIPPED WARNING] Cleanup after skipped case failed: {cleanup_exc}")
                if fail_fast:
                    raise


def main():
    """
    Entry point for the benchmark runner.
    Supports both single-case execution and CSV-based batch execution.
    """

    parser = argparse.ArgumentParser(description="Run network benchmark tests")

    # ===== Execution mode =====
    parser.add_argument(
        "--benchmark-csv",
        type=str,
        default=os.path.join(cur_dir, "benchmark_selected.csv"),
        help="Path to benchmark CSV file (default: benchmark_selected.csv, the held-out test slice)",
    )

    parser.add_argument("--problem", type=str, help="Problem name")
    parser.add_argument("--scenario", type=str, help="Scenario name")
    parser.add_argument("--topo-size", type=str, help="Topology size")

    # ===== Agent configuration =====
    parser.add_argument("--agent-type", type=str, default="react")
    parser.add_argument("--llm-backend", type=str, default="openai")
    parser.add_argument("--model", "--backend-model", dest="model", type=str, default="gpt-5")
    parser.add_argument("--max-steps", type=int, default=20)

    # ===== Evaluation configuration =====
    parser.add_argument("--judge-llm-backend", type=str, default="openai")
    parser.add_argument("--judge-model", type=str, default="gpt-5-mini")
    parser.add_argument(
        "--destroy-env",
        action="store_true",
        help="Destroy the network environment after evaluation",
    )
    parser.add_argument(
        "--auto-recover-stale-env",
        "--ensure-clean-env",
        dest="auto_recover_stale_env",
        action="store_true",
        help=(
            "Before a case starts, and after teardown, detect stale Kathara/Docker runtime "
            "left by previous experiments and clean it. This does not retry or recover the current case."
        ),
    )
    parser.add_argument(
        "--no-auto-recover-stale-env",
        dest="auto_recover_stale_env",
        action="store_false",
        help="Disable stale-runtime recovery. Not recommended for long unattended batch runs.",
    )
    parser.set_defaults(auto_recover_stale_env=True)
    parser.add_argument(
        "--docker-service-name",
        type=str,
        default=None,
        help=(
            "Optional Docker service name for --auto-recover-stale-env. "
            "On Windows the helper tries `com.docker.service` then `docker` by default."
        ),
    )
    parser.add_argument(
        "--recovery-settle-seconds",
        type=int,
        default=180,
        help="Seconds to wait after Docker restart and `kathara wipe` before retrying.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help=(
            "Stop on the first CSV case error. By default CSV mode records a zero-score "
            "setup-skip row and continues to the next case."
        ),
    )

    args = parser.parse_args()

    # Determine execution mode
    if args.problem and args.scenario and args.topo_size:
        # Single benchmark execution
        run_single_benchmark(
            problem=args.problem,
            scenario=args.scenario,
            topo_size=args.topo_size,
            agent_type=args.agent_type,
            llm_backend=args.llm_backend,
            model=args.model,
            max_steps=args.max_steps,
            judge_llm_backend=args.judge_llm_backend,
            judge_model=args.judge_model,
            destroy_env=args.destroy_env,
            auto_recover_stale_env=args.auto_recover_stale_env,
            docker_service_name=args.docker_service_name,
            recovery_settle_seconds=args.recovery_settle_seconds,
        )
    else:
        # CSV-based batch execution
        run_benchmark_from_csv(
            benchmark_file=args.benchmark_csv,
            agent_type=args.agent_type,
            llm_backend=args.llm_backend,
            model=args.model,
            max_steps=args.max_steps,
            judge_llm_backend=args.judge_llm_backend,
            judge_model=args.judge_model,
            destroy_env=args.destroy_env,
            auto_recover_stale_env=args.auto_recover_stale_env,
            docker_service_name=args.docker_service_name,
            recovery_settle_seconds=args.recovery_settle_seconds,
            fail_fast=args.fail_fast,
        )


if __name__ == "__main__":
    main()
