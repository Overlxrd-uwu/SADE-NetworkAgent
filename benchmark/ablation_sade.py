"""
SADE Ablation Study — Compares baseline vs SADE agent on targeted scenarios.

Usage:
    python benchmark/ablation_sade.py --mode run     # Run all ablation experiments
    python benchmark/ablation_sade.py --mode analyze  # Analyze results
    python benchmark/ablation_sade.py --mode both     # Run then analyze

The ablation targets scenarios where the baseline agent performed poorly
(resource contention, load balancer, application delay) — the fault types
that require host-level diagnosis beyond network connectivity checks.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from statistics import mean, stdev

# Setup paths
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CUR_DIR)
SRC_DIR = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)

from scripts.step1_net_env_start import start_net_env
from scripts.step2_failure_inject import inject_failure
from scripts.step3_agent_run import start_agent
from scripts.step4_result_eval import eval_results
from nika.config import RESULTS_DIR

# ──────────────────────────────────────────────────────────────────────
# Ablation experiment definitions
# ──────────────────────────────────────────────────────────────────────

# Problems where baseline scored poorly (1-2/5) — the SADE target scenarios
ABLATION_SCENARIOS = [
    # Resource contention category
    {"problem": "load_balancer_overload",       "scenario": "ospf_enterprise_dhcp", "sizes": ["s", "m", "l"]},
    {"problem": "receiver_resource_contention", "scenario": "ospf_enterprise_dhcp", "sizes": ["s", "m", "l"]},
    {"problem": "sender_application_delay",     "scenario": "ospf_enterprise_dhcp", "sizes": ["s", "m", "l"]},
    {"problem": "sender_resource_contention",   "scenario": "ospf_enterprise_dhcp", "sizes": ["s", "m", "l"]},
]

# Agent configurations to compare
AGENTS = [
    {"agent_type": "claude-code",      "label": "baseline"},
    {"agent_type": "claude-code-sade", "label": "sade"},
]

JUDGE_MODEL = "gpt-5"
MAX_STEPS = 20  # Match existing benchmark config

# Output directory for ablation results
ABLATION_DIR = os.path.join(BASE_DIR, "benchmark", "ablation_results")


def run_single(problem: str, scenario: str, topo_size: str, agent_type: str, label: str) -> dict:
    """
    Run a single ablation experiment and return the result record.
    """
    print(f"\n{'='*70}")
    print(f"  ABLATION: {problem} / {scenario} / {topo_size}")
    print(f"  Agent: {label} ({agent_type})")
    print(f"{'='*70}\n")

    # Step 1: Deploy
    start_net_env(scenario, topo_size=topo_size, redeploy=True)

    # Step 2: Inject fault
    inject_failure(problem_names=[problem])

    # Step 3: Run agent
    start_agent(agent_type=agent_type, backend_model="gpt-5", max_steps=MAX_STEPS)

    # Step 4: Evaluate
    eval_results(judge_model=JUDGE_MODEL, destroy_env=True)

    # Collect results
    result_dir = os.path.join(RESULTS_DIR, problem)
    sessions = sorted(os.listdir(result_dir), reverse=True)
    if not sessions:
        return {"error": "no session found"}

    session_dir = os.path.join(result_dir, sessions[0])
    record = {
        "problem": problem,
        "scenario": scenario,
        "topo_size": topo_size,
        "agent_type": agent_type,
        "label": label,
        "session_id": sessions[0],
        "timestamp": datetime.now().isoformat(),
    }

    # Read ground truth
    gt_path = os.path.join(session_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        with open(gt_path) as f:
            record["ground_truth"] = json.load(f)

    # Read submission
    sub_path = os.path.join(session_dir, "submission.json")
    if os.path.exists(sub_path):
        with open(sub_path) as f:
            record["submission"] = json.load(f)
        record["submitted"] = True
    else:
        record["submitted"] = False

    # Read judge scores
    judge_path = os.path.join(session_dir, "llm_judge.json")
    if os.path.exists(judge_path):
        with open(judge_path) as f:
            judge = json.load(f)
        scores = judge.get("scores", {})
        record["scores"] = {
            k: scores.get(k, {}).get("score", None)
            for k in ["relevance", "correctness", "efficiency", "clarity", "final_outcome", "overall_score"]
        }
    else:
        record["scores"] = {}

    return record


def run_ablation():
    """Run all ablation experiments for both agent types."""
    os.makedirs(ABLATION_DIR, exist_ok=True)
    results = []

    for scenario_def in ABLATION_SCENARIOS:
        for size in scenario_def["sizes"]:
            for agent_def in AGENTS:
                try:
                    record = run_single(
                        problem=scenario_def["problem"],
                        scenario=scenario_def["scenario"],
                        topo_size=size,
                        agent_type=agent_def["agent_type"],
                        label=agent_def["label"],
                    )
                    results.append(record)
                except Exception as e:
                    print(f"ERROR: {scenario_def['problem']}/{size}/{agent_def['label']}: {e}")
                    results.append({
                        "problem": scenario_def["problem"],
                        "scenario": scenario_def["scenario"],
                        "topo_size": size,
                        "label": agent_def["label"],
                        "error": str(e),
                    })

                # Save incrementally
                out_path = os.path.join(ABLATION_DIR, "ablation_raw.json")
                with open(out_path, "w") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nAll ablation experiments complete. Raw results: {out_path}")
    return results


def analyze_results(results_path: str = None):
    """
    Analyze ablation results and produce comparison tables.

    Outputs:
      - ablation_summary.csv   — per-experiment comparison
      - ablation_aggregate.csv — per-problem aggregate statistics
      - ablation_report.txt    — human-readable report
    """
    if results_path is None:
        results_path = os.path.join(ABLATION_DIR, "ablation_raw.json")

    with open(results_path) as f:
        results = json.load(f)

    # ── Per-experiment summary ──
    summary_rows = []
    for r in results:
        if "error" in r and "scores" not in r:
            continue
        scores = r.get("scores", {})
        summary_rows.append({
            "problem": r["problem"],
            "size": r.get("topo_size", "?"),
            "agent": r["label"],
            "submitted": r.get("submitted", False),
            "overall": scores.get("overall_score", "?"),
            "final_outcome": scores.get("final_outcome", "?"),
            "relevance": scores.get("relevance", "?"),
            "correctness": scores.get("correctness", "?"),
            "efficiency": scores.get("efficiency", "?"),
            "clarity": scores.get("clarity", "?"),
        })

    summary_path = os.path.join(ABLATION_DIR, "ablation_summary.csv")
    if summary_rows:
        with open(summary_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)

    # ── Aggregate per-problem statistics ──
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(list))

    for r in results:
        if "error" in r and "scores" not in r:
            continue
        scores = r.get("scores", {})
        overall = scores.get("overall_score")
        if overall is not None and overall != "?":
            key = (r["problem"], r["label"])
            agg[key]["overall"].append(int(overall))
            final = scores.get("final_outcome")
            if final is not None and final != "?":
                agg[key]["final_outcome"].append(int(final))

    agg_rows = []
    for (problem, label), metrics in sorted(agg.items()):
        overall_scores = metrics["overall"]
        final_scores = metrics.get("final_outcome", [])
        agg_rows.append({
            "problem": problem,
            "agent": label,
            "n": len(overall_scores),
            "overall_mean": round(mean(overall_scores), 2) if overall_scores else "?",
            "overall_std": round(stdev(overall_scores), 2) if len(overall_scores) > 1 else 0,
            "final_mean": round(mean(final_scores), 2) if final_scores else "?",
        })

    agg_path = os.path.join(ABLATION_DIR, "ablation_aggregate.csv")
    if agg_rows:
        with open(agg_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=agg_rows[0].keys())
            writer.writeheader()
            writer.writerows(agg_rows)

    # ── Human-readable report ──
    report_lines = [
        "=" * 70,
        "SADE ABLATION STUDY REPORT",
        f"Generated: {datetime.now().isoformat()}",
        f"Total experiments: {len(results)}",
        "=" * 70,
        "",
    ]

    # Group by problem for side-by-side comparison
    from collections import OrderedDict
    by_problem = OrderedDict()
    for r in results:
        if "error" in r and "scores" not in r:
            continue
        p = r["problem"]
        if p not in by_problem:
            by_problem[p] = {"baseline": [], "sade": []}
        by_problem[p][r["label"]].append(r)

    for problem, agents in by_problem.items():
        report_lines.append(f"\n--- {problem} ---")
        report_lines.append(f"{'Size':<6} {'Baseline':>10} {'SADE':>10} {'Delta':>8}")
        report_lines.append("-" * 40)

        baseline_scores = []
        sade_scores = []

        for size in ["s", "m", "l"]:
            b_score = "?"
            s_score = "?"
            for r in agents["baseline"]:
                if r.get("topo_size") == size:
                    b_score = r.get("scores", {}).get("overall_score", "?")
                    if b_score != "?":
                        baseline_scores.append(int(b_score))
            for r in agents["sade"]:
                if r.get("topo_size") == size:
                    s_score = r.get("scores", {}).get("overall_score", "?")
                    if s_score != "?":
                        sade_scores.append(int(s_score))

            delta = ""
            if b_score != "?" and s_score != "?":
                d = int(s_score) - int(b_score)
                delta = f"+{d}" if d > 0 else str(d)

            report_lines.append(f"{size:<6} {str(b_score):>10} {str(s_score):>10} {delta:>8}")

        # Averages
        b_avg = f"{mean(baseline_scores):.1f}" if baseline_scores else "?"
        s_avg = f"{mean(sade_scores):.1f}" if sade_scores else "?"
        report_lines.append("-" * 40)
        report_lines.append(f"{'avg':<6} {b_avg:>10} {s_avg:>10}")

    # Overall summary
    all_baseline = [int(r["scores"]["overall_score"]) for r in results
                    if r.get("label") == "baseline" and r.get("scores", {}).get("overall_score") not in (None, "?")]
    all_sade = [int(r["scores"]["overall_score"]) for r in results
                if r.get("label") == "sade" and r.get("scores", {}).get("overall_score") not in (None, "?")]

    report_lines.append(f"\n{'='*70}")
    report_lines.append("OVERALL SUMMARY")
    report_lines.append(f"{'='*70}")
    if all_baseline:
        report_lines.append(f"Baseline: mean={mean(all_baseline):.2f}, n={len(all_baseline)}")
    if all_sade:
        report_lines.append(f"SADE:     mean={mean(all_sade):.2f}, n={len(all_sade)}")
    if all_baseline and all_sade:
        improvement = mean(all_sade) - mean(all_baseline)
        report_lines.append(f"Delta:    {'+' if improvement > 0 else ''}{improvement:.2f}")

    report = "\n".join(report_lines)
    report_path = os.path.join(ABLATION_DIR, "ablation_report.txt")
    with open(report_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nFiles written:")
    print(f"  {summary_path}")
    print(f"  {agg_path}")
    print(f"  {report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="SADE Ablation Study")
    parser.add_argument("--mode", choices=["run", "analyze", "both"], default="both",
                        help="'run' to execute experiments, 'analyze' to process results, 'both' for full pipeline")
    parser.add_argument("--results-path", type=str, default=None,
                        help="Path to existing ablation_raw.json (for analyze mode)")
    args = parser.parse_args()

    if args.mode in ("run", "both"):
        run_ablation()

    if args.mode in ("analyze", "both"):
        analyze_results(args.results_path)


if __name__ == "__main__":
    main()
