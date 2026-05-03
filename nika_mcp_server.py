"""
NIKA MCP Server — exposes NIKA to the outer Claude Code agent.

Deploys live Kathará container networks, injects faults, runs an inner
diagnosis agent (react/claude-code), and returns the evaluation result.

Flow:
  list_scenarios() / list_problems()
  → start_experiment() → check_experiment() (poll until done) → get_results()
"""

import json
import os
import signal
import subprocess
import sys
import tempfile

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

BASE_DIR = os.getenv("BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Use the project's own venv Python so subprocesses get the right dependencies
_VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe") \
    if sys.platform == "win32" \
    else os.path.join(BASE_DIR, ".venv", "bin", "python")
PYTHON = _VENV_PYTHON if os.path.exists(_VENV_PYTHON) else sys.executable

mcp = FastMCP("nika-assistant")

# Tracks running experiments: job_id → {proc, log_path, problem}
_jobs: dict = {}


@mcp.tool()
def list_scenarios() -> str:
    """List all available network topology scenarios in NIKA."""
    from nika.net_env.net_env_pool import list_all_net_envs
    names = list(list_all_net_envs().keys())
    return "Available network topologies:\n" + "\n".join(f"  - {n}" for n in names)


@mcp.tool()
def list_problems() -> str:
    """List all available fault/problem types that can be injected into the network."""
    from nika.orchestrator.problems.prob_pool import list_avail_problem_names
    names = list_avail_problem_names()
    return "Available fault types:\n" + "\n".join(f"  - {n}" for n in sorted(names))


@mcp.tool()
def start_experiment(
    scenario: str,
    problem: str,
    topo_size: str = "s",
    target_devices: str = "",
    agent_type: str = "react",
    backend_model: str = "gpt-5",
    judge_model: str = "gpt-5",
) -> str:
    """
    Launch a NIKA experiment in the background and return a job ID immediately.
    The experiment deploys a network, injects a fault, runs an inner diagnosis
    agent, and evaluates the result.

    Args:
        scenario:        Topology name (e.g. 'dc_clos_bgp'). Use list_scenarios() to see options.
        problem:         Fault type (e.g. 'host_crash'). Use list_problems() to see options.
                         For multiple faults, use comma-separated values: 'host_crash,host_crash'.
        topo_size:       's' (small), 'm' (medium), 'l' (large). Default: 's'.
        target_devices:  Optional comma-separated device names to target (e.g. 'pc_0_0' or 'pc_0_0,pc_0_1').
                         If omitted, devices are chosen randomly.
        agent_type:      Inner diagnosis agent type: 'react' (LangGraph + any LLM),
                         'claude-code' (Claude Code SDK), or 'claude-code-sade'
                         (SADE-enhanced Claude Code with layered escalation). Default: 'react'.
        backend_model:   LLM for the inner agent (e.g. 'deepseek-chat', 'gpt-5',
                         'claude-sonnet-4-6'). Ignored when agent_type='claude-code'.
                         Default: 'deepseek-chat'.
        judge_model:     LLM used for the LLM-as-Judge evaluation step. Default: 'deepseek-chat'.

    Returns:
        A job_id you can pass to check_experiment() and get_results().
    """
    log_fd, log_path = tempfile.mkstemp(prefix="nika_", suffix=".log", text=True)
    os.close(log_fd)

    benchmark_script = os.path.join(BASE_DIR, "benchmark", "run_benchmark.py")

    cmd = [
        PYTHON, "-u", benchmark_script,
        "--scenario", scenario,
        "--problem", problem,
        "--topo-size", topo_size,
        "--agent-type", agent_type,
        "--backend-model", backend_model,
        "--max-steps", "30",
        "--judge-model", judge_model,
        "--destroy-env",
    ]
    if target_devices:
        cmd += ["--target-devices", target_devices]

    env = os.environ.copy()
    env["BASE_DIR"] = BASE_DIR
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("CLAUDECODE", None)  # allow nested Claude Code SDK sessions
    env.pop("ANTHROPIC_API_KEY", None)  # force inner agent to use Pro plan OAuth

    popen_kwargs = {}
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        cmd,
        stdout=open(log_path, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        cwd=BASE_DIR,
        env=env,
        **popen_kwargs,
    )

    job_id = f"job_{proc.pid}"
    root_cause = "multiple_faults" if "," in problem else problem.strip()
    _jobs[job_id] = {"proc": proc, "log_path": log_path, "problem": root_cause}

    targets_info = f"\n  Targets  : {target_devices}" if target_devices else ""
    return (
        f"Experiment started (job_id={job_id})\n"
        f"  Topology : {scenario} (size={topo_size})\n"
        f"  Fault    : {problem}{targets_info}\n"
        f"  Agent    : {agent_type} / {backend_model}\n"
        f"  PID      : {proc.pid}\n"
        f"  Log      : {log_path}\n\n"
        f"Use check_experiment('{job_id}') to see progress.\n"
        f"Use get_results('{job_id}') to get the final answer (when done)."
    )


@mcp.tool()
def check_experiment(job_id: str, last_n_lines: int = 20) -> str:
    """
    Check the status and recent log output of a running experiment.

    Args:
        job_id:       The ID returned by start_experiment().
        last_n_lines: How many recent log lines to show (default: 20).

    Returns:
        Status (running/done/failed) and the last N lines of output.
    """
    if job_id not in _jobs:
        return f"Unknown job_id '{job_id}'. Use start_experiment() first."

    job = _jobs[job_id]
    proc = job["proc"]
    log_path = job["log_path"]

    # Check if finished
    ret = proc.poll()
    if ret is None:
        status = "RUNNING"
    elif ret == 0:
        status = "DONE (success)"
    else:
        status = f"DONE (failed, exit code {ret})"

    # Read last N lines of log
    try:
        with open(log_path) as f:
            lines = f.readlines()
        tail = "".join(lines[-last_n_lines:]) if lines else "(no output yet)"
    except Exception as e:
        tail = f"(could not read log: {e})"

    return f"Status: {status}\n\nRecent output:\n{tail}"


@mcp.tool()
def stop_experiment(job_id: str) -> str:
    """
    Stop a running experiment (single or batch). Terminates the process and
    all its children (inner agent, Kathará containers, etc.).

    Already-completed experiment cases keep their results in the results/ folder.

    Args:
        job_id: The ID returned by start_experiment() or start_batch_experiment().

    Returns:
        Confirmation that the experiment was stopped.
    """
    if job_id not in _jobs:
        return f"Unknown job_id '{job_id}'. Active jobs: {list(_jobs.keys()) or '(none)'}"

    job = _jobs[job_id]
    proc = job["proc"]

    ret = proc.poll()
    if ret is not None:
        return f"Job '{job_id}' already finished (exit code {ret}). Nothing to stop."

    pid = proc.pid
    try:
        # Kill the entire process tree (benchmark → step scripts → containers)
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

    proc.wait(timeout=10)

    return (
        f"Stopped job '{job_id}' (PID {pid}).\n"
        f"Results from already-completed cases are still available in results/.\n"
        f"Log file: {job['log_path']}"
    )


@mcp.tool()
def get_results(job_id: str) -> str:
    """
    Get the final diagnosis results for a completed experiment.
    Call check_experiment() first to confirm the job is done.

    Args:
        job_id: The ID returned by start_experiment().

    Returns:
        Ground truth, Claude's diagnosis, and evaluation score.
    """
    if job_id not in _jobs:
        return f"Unknown job_id '{job_id}'. Use start_experiment() first."

    job = _jobs[job_id]
    proc = job["proc"]
    problem = job["problem"]

    ret = proc.poll()
    if ret is None:
        return "Experiment is still running. Use check_experiment() to monitor progress."
    if ret != 0:
        return f"Experiment failed (exit code {ret}). Use check_experiment() to see the error log."

    results_dir = os.path.join(BASE_DIR, "results", problem)
    if not os.path.exists(results_dir):
        return "Results directory not found."

    sessions = sorted(os.listdir(results_dir), reverse=True)
    if not sessions:
        return "No sessions found in results."

    session_dir = os.path.join(results_dir, sessions[0])
    lines = [f"=== Experiment Results (session {sessions[0]}) ==="]

    gt_path = os.path.join(session_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        gt = json.loads(open(gt_path).read())
        lines.append("\nGround Truth:")
        lines.append(f"  Anomaly detected : {gt.get('is_anomaly')}")
        lines.append(f"  Faulty devices   : {gt.get('faulty_devices', [])}")
        lines.append(f"  Root cause       : {gt.get('root_cause_name', [])}")

    sub_path = os.path.join(session_dir, "submission.json")
    if os.path.exists(sub_path):
        sub = json.loads(open(sub_path).read())
        lines.append("\nClaude's Diagnosis:")
        lines.append(f"  Anomaly detected : {sub.get('is_anomaly')}")
        lines.append(f"  Faulty devices   : {sub.get('faulty_devices', [])}")
        lines.append(f"  Root cause       : {sub.get('root_cause_name', [])}")
    else:
        lines.append("\nClaude did not submit an answer.")

    judge_path = os.path.join(session_dir, "llm_judge.json")
    if os.path.exists(judge_path):
        try:
            judge = json.loads(open(judge_path).read())
            scores = judge.get("scores", {})
            lines.append("\nEvaluation Scores (1–5):")
            for key in ["relevance", "correctness", "efficiency", "clarity", "final_outcome"]:
                val = scores.get(key, {}).get("score", "?")
                lines.append(f"  {key:<16}: {val}")
            overall = scores.get("overall_score", {}).get("score", "?")
            lines.append(f"  {'overall':<16}: {overall}")
        except Exception:
            pass

    return "\n".join(lines)

if __name__ == "__main__":
    mcp.run()
