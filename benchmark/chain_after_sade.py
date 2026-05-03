"""Wait for the running SADE benchmark to finish, archive `results/`, then
launch a claude-code (base) run on a different CSV.

Why archive: `run_benchmark.py` always writes into `results/`. Without renaming
between runs, the SADE session tree and the claude-code session tree (plus
their `evaluation_summary.csv` rows) would mix into the same folder, making
later analysis ambiguous.

Usage:
    # 1. Find the PID of the currently-running SADE process
    #    PowerShell:
    #        Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    #          Where-Object { $_.CommandLine -like '*run_benchmark*' } |
    #          Select-Object ProcessId, CommandLine
    #
    # 2. Run this watcher with that PID
    python benchmark/chain_after_sade.py --pid 12345
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CUR_DIR = Path(__file__).resolve().parent
BASE_DIR = CUR_DIR.parent
RESULTS_DIR = BASE_DIR / "results"
RUN_BENCHMARK = CUR_DIR / "run_benchmark.py"


def pid_alive(pid: int) -> bool:
    """True if pid still exists. Uses psutil if available, else platform fallback."""
    try:
        import psutil  # type: ignore
        return psutil.pid_exists(pid)
    except ImportError:
        pass

    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def wait_for_pid(pid: int, poll_seconds: int) -> None:
    print(f"[CHAIN] Watching PID {pid} (polling every {poll_seconds}s)...")
    while pid_alive(pid):
        time.sleep(poll_seconds)
    print(f"[CHAIN] PID {pid} exited.")


def archive_results(target_name: str) -> Path:
    if not RESULTS_DIR.exists():
        raise RuntimeError(f"Cannot archive: {RESULTS_DIR} does not exist")
    archive = BASE_DIR / target_name
    if archive.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = BASE_DIR / f"{target_name}_{ts}"
        print(f"[CHAIN] {target_name} already exists; using {archive.name} instead")
    shutil.move(str(RESULTS_DIR), str(archive))
    print(f"[CHAIN] results/ -> {archive}")
    return archive


def run_next(csv_path: str, agent_type: str, max_steps: int) -> int:
    cmd = [
        sys.executable,
        str(RUN_BENCHMARK),
        "--benchmark-csv", csv_path,
        "--agent-type", agent_type,
        "--max-steps", str(max_steps),
        "--destroy-env",
        "--auto-recover-stale-env",
    ]
    print(f"[CHAIN] Launching: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(BASE_DIR)).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--pid", type=int, default=None,
                        help="PID of a currently-running benchmark process to wait for. "
                             "If omitted, skip the wait + first archive and just run the next benchmark.")
    parser.add_argument("--archive-as", default="results_sade",
                        help="Folder name to rename results/ to after SADE finishes (default: results_sade)")
    parser.add_argument("--next-csv", default=str(CUR_DIR / "benchmark_failed.csv"),
                        help="CSV for the follow-up run (default: benchmark/benchmark_failed.csv)")
    parser.add_argument("--next-agent", default="claude-code",
                        help="Agent type for the follow-up run (default: claude-code)")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--final-archive-as", default="results_claude_code",
                        help="Folder name to rename results/ to after the follow-up run finishes "
                             "(default: results_claude_code)")
    args = parser.parse_args()

    next_csv = Path(args.next_csv).resolve()
    if not next_csv.exists():
        print(f"[CHAIN] ERROR: {next_csv} does not exist")
        sys.exit(2)

    if args.pid is not None:
        if not pid_alive(args.pid):
            print(f"[CHAIN] ERROR: PID {args.pid} is not alive. Was the run already done? "
                  "If so, re-invoke without --pid to skip the wait + first archive.")
            sys.exit(1)
        wait_for_pid(args.pid, args.poll_seconds)
        if RESULTS_DIR.exists():
            archive_results(args.archive_as)
        else:
            print(f"[CHAIN] No {RESULTS_DIR} to archive at first stage; skipping first archive.")
    else:
        print("[CHAIN] No --pid given; skipping wait + first archive, going straight to next run.")

    try:
        rc = run_next(str(next_csv), args.next_agent, args.max_steps)
    finally:
        if RESULTS_DIR.exists():
            archive_results(args.final_archive_as)
        else:
            print(f"[CHAIN] No {RESULTS_DIR} to archive at end (follow-up wrote nothing).")
    sys.exit(rc)


if __name__ == "__main__":
    main()
