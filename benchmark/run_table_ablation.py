"""Run the without-table vs with-table ablation on a 10-case subset.

Default flow:
    1. Verify skills are in WITH TABLE state.
    2. Strip decision tables (OSPF / link / BGP).
    3. Pass 1 (without_table): run benchmark_table_ablation.csv.
    4. Restore decision tables (in `finally` so repo recovers even on crash).
    5. Pass 2 (with_table): re-run the same CSV.
    6. Diff evaluation_summary.csv around each pass to recover that pass's rows.
    7. Write per-pass result CSVs and a comparison summary.

Usage:
    python benchmark/run_table_ablation.py
    python benchmark/run_table_ablation.py --skip-with-table     # only no-table pass
    python benchmark/run_table_ablation.py --skip-without-table  # only with-table pass
    python benchmark/run_table_ablation.py --no-restore          # leave stripped at end
"""
import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CUR_DIR = Path(__file__).resolve().parent
BASE_DIR = CUR_DIR.parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from nika.config import RESULTS_DIR  # noqa: E402

CSV_PATH = CUR_DIR / "benchmark_table_ablation.csv"
TOGGLE_SCRIPT = CUR_DIR / "toggle_decision_tables.py"
RUN_BENCHMARK = CUR_DIR / "run_benchmark.py"
OUT_DIR = CUR_DIR / "table_ablation_results"
EVAL_SUMMARY = Path(RESULTS_DIR) / "0_summary" / "evaluation_summary.csv"

AGENT_TYPE = "claude-code-sade"
LLM_BACKEND = "openai"
MODEL = "gpt-5"
MAX_STEPS = 20
JUDGE_BACKEND = "openai"
JUDGE_MODEL = "gpt-5-mini"


def read_eval_rows() -> list[dict]:
    if not EVAL_SUMMARY.exists():
        return []
    with EVAL_SUMMARY.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def diff_eval_rows(before: list[dict], after: list[dict]) -> list[dict]:
    before_ids = {row.get("session_id") for row in before}
    return [row for row in after if row.get("session_id") not in before_ids]


def call_toggle(action: str) -> None:
    print(f"\n[TOGGLE] {action}")
    result = subprocess.run(
        [sys.executable, str(TOGGLE_SCRIPT), action],
        cwd=str(BASE_DIR),
    )
    if result.returncode != 0:
        raise RuntimeError(f"toggle_decision_tables.py {action} failed (rc={result.returncode})")


def run_pass(label: str) -> list[dict]:
    print(f"\n{'=' * 70}")
    print(f"  PASS: {label}")
    print(f"  CSV:  {CSV_PATH.name}")
    print(f"  Agent: {AGENT_TYPE}, max_steps={MAX_STEPS}")
    print(f"  Started: {datetime.now().isoformat(timespec='seconds')}")
    print(f"{'=' * 70}\n")

    before = read_eval_rows()
    cmd = [
        sys.executable,
        str(RUN_BENCHMARK),
        "--benchmark-csv", str(CSV_PATH),
        "--agent-type", AGENT_TYPE,
        "--llm-backend", LLM_BACKEND,
        "--model", MODEL,
        "--max-steps", str(MAX_STEPS),
        "--judge-llm-backend", JUDGE_BACKEND,
        "--judge-model", JUDGE_MODEL,
        "--destroy-env",
        "--auto-recover-stale-env",
    ]
    subprocess.run(cmd, cwd=str(BASE_DIR))
    after = read_eval_rows()
    new_rows = diff_eval_rows(before, after)
    print(f"\n[PASS DONE] {label}: {len(new_rows)} new rows in evaluation_summary.csv")
    return new_rows


def write_pass_results(label: str, rows: list[dict]) -> Path | None:
    if not rows:
        print(f"[OUT] {label}: no rows to write")
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{label}_results.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OUT] {path} ({len(rows)} rows)")
    return path


def avg(rows: list[dict], key: str) -> float | None:
    vals: list[float] = []
    for r in rows:
        v = r.get(key)
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            pass
    return sum(vals) / len(vals) if vals else None


SUMMARY_KEYS = [
    "llm_judge_overall_score",
    "llm_judge_correctness_score",
    "llm_judge_final_outcome_score",
    "rca_f1",
    "localization_f1",
]


def summarize(with_rows: list[dict], without_rows: list[dict]) -> None:
    print("\n" + "=" * 90)
    print("  COMPARISON: with_table vs without_table")
    print("=" * 90)

    header_cols = " ".join(
        f"{k.replace('llm_judge_', '').replace('_score', ''):>16s}" for k in SUMMARY_KEYS
    )
    print(f"\n  Pass             n  {header_cols}")
    for label, rows in [("with_table", with_rows), ("without_table", without_rows)]:
        cols = []
        for k in SUMMARY_KEYS:
            v = avg(rows, k)
            cols.append(f"{v:>16.3f}" if v is not None else f"{'?':>16s}")
        print(f"  {label:<14s} {len(rows):>3d}  {' '.join(cols)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "comparison_summary.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pass", "n"] + SUMMARY_KEYS)
        for label, rows in [("with_table", with_rows), ("without_table", without_rows)]:
            row_avgs = [avg(rows, k) for k in SUMMARY_KEYS]
            writer.writerow(
                [label, len(rows)]
                + [f"{v:.3f}" if v is not None else "" for v in row_avgs]
            )
    print(f"\n[OUT] {out_csv}")


def per_problem_table(with_rows: list[dict], without_rows: list[dict]) -> None:
    """Print per-problem overall_score side by side for quick eyeballing."""
    keyfn = lambda r: (r.get("root_cause_name", ""), r.get("net_env", ""), r.get("scenario_topo_size", ""))
    with_map = {keyfn(r): r for r in with_rows}
    without_map = {keyfn(r): r for r in without_rows}
    keys = sorted(set(with_map) | set(without_map))

    print("\n  Per-problem overall_score (rca_f1):")
    print(f"  {'problem':<36s} {'scenario':<24s} {'size':<5s} {'WITH':>10s} {'WITHOUT':>10s} {'Δ':>8s}")
    print("  " + "-" * 96)
    for k in keys:
        prob, scen, size = k
        w = with_map.get(k, {})
        wo = without_map.get(k, {})

        def fmt(row: dict, score_key: str, f1_key: str) -> str:
            score = row.get(score_key)
            f1 = row.get(f1_key)
            try:
                return f"{float(score):.0f} ({float(f1):.2f})"
            except (TypeError, ValueError):
                return "?"

        w_str = fmt(w, "llm_judge_overall_score", "rca_f1") if w else "-"
        wo_str = fmt(wo, "llm_judge_overall_score", "rca_f1") if wo else "-"
        try:
            delta_score = float(wo.get("llm_judge_overall_score")) - float(w.get("llm_judge_overall_score"))
            delta_str = f"{delta_score:+.0f}"
        except (TypeError, ValueError):
            delta_str = "?"
        print(f"  {prob:<36s} {scen:<24s} {size:<5s} {w_str:>10s} {wo_str:>10s} {delta_str:>8s}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--skip-without-table", action="store_true",
                        help="Skip the without_table pass (no strip, no restore)")
    parser.add_argument("--skip-with-table", action="store_true",
                        help="Skip the with_table pass (assume already run)")
    parser.add_argument("--no-restore", action="store_true",
                        help="Don't restore decision tables at end")
    args = parser.parse_args()

    print("Table-ablation benchmark")
    print(f"  CSV:    {CSV_PATH}")
    print(f"  Cases:  10 × 2 passes = up to 20 benchmark runs")
    print(f"  Agent:  {AGENT_TYPE}")
    print(f"  Output: {OUT_DIR}")

    print("\n[STATUS] Pre-flight check:")
    call_toggle("status")

    # Pass 1: without_table — strip first, then run, then restore (in finally
    # so the repo returns to the original state even if the pass crashes).
    without_rows: list[dict] = []
    if not args.skip_without_table:
        call_toggle("strip")
        try:
            without_rows = run_pass("without_table")
            write_pass_results("without_table", without_rows)
        finally:
            if not args.no_restore:
                call_toggle("restore")
            else:
                print("[NOTE] --no-restore: skills remain stripped. "
                      "Run `python benchmark/toggle_decision_tables.py restore` when ready.")
    else:
        prev = OUT_DIR / "without_table_results.csv"
        if prev.exists():
            with prev.open(newline="", encoding="utf-8") as f:
                without_rows = list(csv.DictReader(f))
            print(f"[SKIP] Loaded {len(without_rows)} prior without_table rows from {prev}")

    # Pass 2: with_table — original skills, no toggle needed.
    with_rows: list[dict] = []
    if not args.skip_with_table:
        with_rows = run_pass("with_table")
        write_pass_results("with_table", with_rows)
    else:
        prev = OUT_DIR / "with_table_results.csv"
        if prev.exists():
            with prev.open(newline="", encoding="utf-8") as f:
                with_rows = list(csv.DictReader(f))
            print(f"[SKIP] Loaded {len(with_rows)} prior with_table rows from {prev}")

    print("\n[STATUS] Post-run check:")
    call_toggle("status")

    summarize(with_rows, without_rows)
    per_problem_table(with_rows, without_rows)


if __name__ == "__main__":
    main()
