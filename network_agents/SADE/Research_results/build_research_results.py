"""Build every Research_results figure in one shot.

Single entry point. From the repo root, run:

    pip install matplotlib numpy pandas
    python Research_results/build_research_results.py

That regenerates every PNG in Research_results/figures/. No tables, no
sidecars — this script generates figures only.

Inputs are read from the per-agent result directories committed under
Research_results/results_{ReAct_GPT5,ClaudeB,sade}/. fig07 (NIKA-limits)
needs an extra dataset that is NOT in this repo; it skips cleanly unless
you set NIKA_LIMITS_DIR to a local directory containing
results_manual_injection/ and results_train_obs/.

Pipeline:
  1. Load 3-way test-set CSVs (ReAct/GPT-5, CC-Baseline/Sonnet, SADE/Sonnet),
     match on (problem, scenario, topo_size) triples, persist
     data/unified_test_3way.csv.
  2. Scan every session's conversation_diagnosis_agent.log for tool_end
     events with is_error=true (the runner's tool_errors CSV column is
     unreliable for Claude-Code agents); persist
     data/tool_errors_from_logs.csv. Required by fig09.
  3. Render 11 publication figures into figures/. fig07 also persists
     data/nika_failure_breakdown.csv (manual_injection + train_obs
     outcomes plus deployment-skip rows) used by the discussion's
     NIKA-injector audit table.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- PATHS
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Research_results"
DATA = OUT / "data"
FIGS = OUT / "figures"
for d in (DATA, FIGS):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- DATASETS
DATASETS = {
    "ReAct (GPT-5)": OUT / "results_ReAct_GPT5" / "results" / "0_summary" / "evaluation_summary.csv",
    "CC-Baseline":   OUT / "results_ClaudeB" / "0_summary" / "evaluation_summary.csv",
    "SADE":          OUT / "results_sade" / "0_summary" / "evaluation_summary.csv",
}

# Per-agent session roots (for log scanning).
SESSION_ROOTS = {
    "ReAct (GPT-5)": OUT / "results_ReAct_GPT5" / "results",
    "CC-Baseline":   OUT / "results_ClaudeB",
    "SADE":          OUT / "results_sade",
}

# NIKA-limits sources for fig07 (both SADE-driven runs; data is NOT
# committed to this repo). Override with the NIKA_LIMITS_DIR environment
# variable; otherwise fig07 will skip cleanly.
_nika_dir = Path(os.environ["NIKA_LIMITS_DIR"]) if os.environ.get("NIKA_LIMITS_DIR") else None
NIKA_SOURCES = {
    "manual_injection": (_nika_dir / "results_manual_injection" / "0_summary" / "evaluation_summary.csv") if _nika_dir else Path("nonexistent_nika_manual_injection.csv"),
    "train_obs":        (_nika_dir / "results_train_obs" / "0_summary" / "evaluation_summary.csv") if _nika_dir else Path("nonexistent_nika_train_obs.csv"),
    "skips_test":       OUT / "results_sade" / "0_summary" / "benchmark_skips.csv",
}

NUMERIC_COLS = [
    "in_tokens", "out_tokens", "steps", "tool_calls", "tool_errors", "time_taken",
    "llm_judge_relevance_score", "llm_judge_correctness_score", "llm_judge_efficiency_score",
    "llm_judge_clarity_score", "llm_judge_final_outcome_score", "llm_judge_overall_score",
    "detection_score", "localization_accuracy", "localization_precision",
    "localization_recall", "localization_f1", "rca_accuracy", "rca_precision",
    "rca_recall", "rca_f1",
]

AGENT_ORDER = ["ReAct (GPT-5)", "CC-Baseline", "SADE"]
AGENT_COLOR = {
    "ReAct (GPT-5)": "#7a6f9b",  # muted purple
    "CC-Baseline":   "#c47236",  # warm earth
    "SADE":          "#3a6fb0",  # muted blue
}
ERROR_PREFIXES = ("[TIMEOUT]", "Machine ", "Error:", "Traceback", "ERROR:")


# ================================================================ STEP 1 — LOAD
def load_csv(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["agent"] = label
    df["triple"] = list(zip(df["root_cause_name"], df["net_env"], df["scenario_topo_size"]))
    return df


frames: dict[str, pd.DataFrame] = {}
for label, p in DATASETS.items():
    if p.is_file():
        frames[label] = load_csv(p, label)
    else:
        print(f"WARN: missing {p}")

print(f"Loaded {len(frames)} test-set datasets:")
for label, df in frames.items():
    print(f"  {label:<16} rows={len(df):>4}  unique_triples={df['triple'].nunique():>4}")
print()

common = set.intersection(*(set(frames[a]["triple"]) for a in AGENT_ORDER))
print(f"3-way matched triples (test set): {len(common)}")

unified = pd.concat(
    [frames[a][frames[a]["triple"].isin(common)] for a in AGENT_ORDER],
    ignore_index=True,
)
unified["session_id"] = unified["session_id"].astype(str).str.zfill(10)
unified.to_csv(DATA / "unified_test_3way.csv", index=False)
print()


# ================================================================ STEP 2 — LOG SCAN (tool errors)
def scan_log_for_errors(log: Path) -> tuple[int, int]:
    """Return (is_err_count, txt_err_count). -1/-1 if log missing."""
    is_err = 0
    txt_err = 0
    if not log.is_file():
        return -1, -1
    try:
        with log.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evt.get("event") != "tool_end":
                    continue
                if evt.get("is_error") is True:
                    is_err += 1
                out = str(evt.get("output", ""))
                if any(out.startswith(p) for p in ERROR_PREFIXES):
                    txt_err += 1
    except OSError:
        return -1, -1
    return is_err, txt_err


def build_tool_errors_csv() -> Path:
    """Walk every session log, count is_error events, persist a CSV.

    Required input for fig09 — the runner's `tool_errors` CSV column reports 0
    for both Claude-Code agents because the SDK's is_error flag isn't wired
    into CSV writing. We rebuild a log-truth count instead.
    """
    out_rows = []
    for a, root in SESSION_ROOTS.items():
        sub = unified[unified["agent"] == a]
        print(f"  scanning {a}: {len(sub)} sessions", flush=True)
        for _, r in sub.iterrows():
            log = (root / r["root_cause_name"] / r["session_id"]
                   / "conversation_diagnosis_agent.log")
            is_err, txt_err = scan_log_for_errors(log)
            out_rows.append({
                "agent": a,
                "root_cause_name": r["root_cause_name"],
                "net_env": r["net_env"],
                "scenario_topo_size": r["scenario_topo_size"],
                "session_id": r["session_id"],
                "csv_tool_errors": int(r["tool_errors"]) if pd.notna(r["tool_errors"]) else 0,
                "log_is_err": is_err,
                "log_txt_err": txt_err,
                "log_any_err": (is_err if is_err >= 0 else 0)
                               + (txt_err if txt_err >= 0 else 0),
            })
    out_df = pd.DataFrame(out_rows)
    out_path = DATA / "tool_errors_from_logs.csv"
    out_df.to_csv(out_path, index=False)
    print(f"  wrote {out_path}")
    return out_path


print("Scanning conversation logs for tool errors:")
build_tool_errors_csv()
print()


# ================================================================ STEP 3 — FIGURES
plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
})


def fig01_headline():
    """Three-panel headline: Overall / RCA F1 / Detection."""
    panels = [
        ("llm_judge_overall_score", "Overall judge (1-5)"),
        ("rca_f1", "RCA F1"),
        ("detection_score", "Detection accuracy"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
    for ax, (col, title) in zip(axes, panels):
        means, errs = [], []
        for a in AGENT_ORDER:
            d = unified[unified["agent"] == a][col]
            d = d.clip(lower=0).dropna() if "f1" in col else d.dropna()
            means.append(d.mean())
            errs.append(d.std() / np.sqrt(len(d)) if len(d) else 0)
        x = np.arange(len(AGENT_ORDER))
        colors = [AGENT_COLOR[a] for a in AGENT_ORDER]
        ax.bar(x, means, yerr=errs, color=colors, capsize=3,
               edgecolor="black", linewidth=0.5, error_kw={"alpha": 0.7}, width=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=9)
        ax.set_title(title, fontsize=11)
        if max(means) > 0:
            ax.set_ylim(0, max(means) * 1.32)
        ax.grid(axis="y", linestyle=":", alpha=0.4)
        for xi, m in zip(x, means):
            ax.text(xi, m + max(means) * 0.04, f"{m:.2f}",
                    ha="center", fontsize=9, fontweight="bold")
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=AGENT_COLOR[a]) for a in AGENT_ORDER]
    legend_labels = ["ReAct (GPT-5, original NIKA baseline)",
                     "CC-Baseline (Claude Code, no SADE)",
                     "SADE (Claude Code + SADE workflow)"]
    fig.legend(legend_handles, legend_labels, loc="lower center", ncol=3,
               frameon=False, bbox_to_anchor=(0.5, -0.06), fontsize=9)
    fig.suptitle(f"Test-set headline metrics (n={len(common)} matched triples; error bars = SEM)",
                 fontsize=11, y=1.02)
    fig.savefig(FIGS / "fig01_headline.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig01_headline.png'}")


def fig02_per_family():
    """Heatmap: mean overall judge score per (fault family x agent)."""
    families = sorted(set(unified["root_cause_name"]))
    matrix = np.full((len(families), len(AGENT_ORDER)), np.nan)
    for i, fam in enumerate(families):
        for j, a in enumerate(AGENT_ORDER):
            d = unified[(unified["root_cause_name"] == fam) & (unified["agent"] == a)]["llm_judge_overall_score"].dropna()
            if len(d):
                matrix[i, j] = d.mean()
    fig, ax = plt.subplots(figsize=(6.3, max(5, len(families) * 0.27)))
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=1, vmax=5)
    ax.set_xticks(range(len(AGENT_ORDER)))
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Baseline", "SADE"], rotation=0)
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(families, fontsize=8)
    for i in range(len(families)):
        for j in range(len(AGENT_ORDER)):
            v = matrix[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                        color="black" if v > 2.5 else "white", fontsize=7.5)
    cb = plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Mean overall judge score (1-5)", fontsize=8)
    ax.set_title(f"Per fault-family overall score (test, {len(common)} matched triples)")
    fig.savefig(FIGS / "fig02_per_family.png")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig02_per_family.png'}")


def fig02_per_category():
    """Compact six-row bar chart by NIKA root_cause_category (paper version)."""
    CAT_ORDER = [
        "misconfiguration", "link_failure", "network_under_attack",
        "resource_contention", "end_host_failure", "network_node_error",
    ]
    CAT_LABEL = {
        "misconfiguration": "Misconfiguration",
        "link_failure": "Link failure",
        "network_under_attack": "Network attack",
        "resource_contention": "Resource contention",
        "end_host_failure": "End-host failure",
        "network_node_error": "Network-node error",
    }
    means = {a: [] for a in AGENT_ORDER}
    sems = {a: [] for a in AGENT_ORDER}
    ns = []
    for cat in CAT_ORDER:
        sub_cat = unified[unified["root_cause_category"] == cat]
        ns.append(int((sub_cat["agent"] == AGENT_ORDER[0]).sum()))
        for a in AGENT_ORDER:
            s = sub_cat[sub_cat["agent"] == a]["llm_judge_overall_score"].dropna()
            means[a].append(s.mean() if len(s) else float("nan"))
            sems[a].append(s.std() / np.sqrt(len(s)) if len(s) else 0)

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    y = np.arange(len(CAT_ORDER))
    h = 0.27
    for i, a in enumerate(AGENT_ORDER):
        offset = (i - 1) * h
        ax.barh(y + offset, means[a], height=h, xerr=sems[a],
                color=AGENT_COLOR[a], edgecolor="black", linewidth=0.4,
                error_kw={"alpha": 0.6, "linewidth": 0.7}, label=a)
        for yi, m in zip(y + offset, means[a]):
            if m == m:
                ax.text(m + 0.05, yi, f"{m:.2f}", va="center",
                        fontsize=8, fontweight="bold")

    ax.set_yticks(y)
    labels_with_n = [f"{CAT_LABEL[c]}\n(n={n})" for c, n in zip(CAT_ORDER, ns)]
    ax.set_yticklabels(labels_with_n, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 5.6)
    ax.set_xlabel("Mean LLM-judge overall score (1-5)")
    ax.axvline(4.0, color="grey", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13),
              frameon=False, fontsize=9, ncol=3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig02_per_category.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig02_per_category.png'}")


def fig03_efficiency():
    """Cost-vs-correctness scatter (in_tokens vs overall judge, jittered)."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    rng = np.random.default_rng(42)
    for a in AGENT_ORDER:
        sub = unified[unified["agent"] == a].dropna(subset=["in_tokens", "llm_judge_overall_score"])
        if not len(sub):
            continue
        jit = rng.uniform(-0.14, 0.14, size=len(sub))
        ax.scatter(sub["in_tokens"] / 1000,
                   sub["llm_judge_overall_score"] + jit,
                   c=AGENT_COLOR[a], s=18, alpha=0.55, edgecolor="none", label=a)
    ax.set_xlabel("input tokens (thousands)")
    ax.set_ylabel("overall judge score (1-5, jittered)")
    ax.set_title(f"Cost vs. correctness (test, n={len(common)})")
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.grid(linestyle=":", alpha=0.4)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(FIGS / "fig03_efficiency.png")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig03_efficiency.png'}")


def fig04_token_budget():
    """Per-session input-token boxplot with median annotations."""
    fig, ax = plt.subplots(figsize=(7, 3.8))
    data = [unified[unified["agent"] == a]["in_tokens"].dropna() / 1000 for a in AGENT_ORDER]
    bp = ax.boxplot(data, tick_labels=AGENT_ORDER, showfliers=False, patch_artist=True)
    for patch, a in zip(bp["boxes"], AGENT_ORDER):
        patch.set_facecolor(AGENT_COLOR[a])
        patch.set_alpha(0.75)
    for i, d in enumerate(data, start=1):
        ax.text(i, d.median(), f"{int(d.median())}k", ha="center", va="bottom",
                fontsize=8, fontweight="bold")
    ax.set_ylabel("input tokens (thousands)")
    ax.set_title(f"Per-session input-token budget (test, n={len(common)})")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    fig.savefig(FIGS / "fig04_token_budget.png")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig04_token_budget.png'}")


def fig05_no_submission_rate():
    """% of sessions where every loc/RCA metric is -1 (no parseable submit)."""
    loc_rca_cols = ["localization_accuracy", "localization_precision",
                    "localization_recall", "localization_f1",
                    "rca_accuracy", "rca_precision",
                    "rca_recall", "rca_f1"]
    no_sub_mask = (unified[loc_rca_cols] == -1).all(axis=1)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    counts, totals, pcts = [], [], []
    for a in AGENT_ORDER:
        m = (unified["agent"] == a)
        n = int(m.sum())
        k = int((m & no_sub_mask).sum())
        counts.append(k); totals.append(n)
        pcts.append(k / n * 100 if n else 0)
    x = np.arange(len(AGENT_ORDER))
    colors = [AGENT_COLOR[a] for a in AGENT_ORDER]
    ax.bar(x, pcts, color=colors, edgecolor="black", linewidth=0.5, width=0.55)
    for xi, p, k, n in zip(x, pcts, counts, totals):
        ax.text(xi, p + max(pcts) * 0.04,
                f"{p:.1f}%\n({k}/{n})",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=10)
    ax.set_ylabel("% of sessions with no submission")
    ax.set_ylim(0, max(pcts) * 1.32)
    ax.set_title(f"No-submission rate per agent (test, n={len(common)} matched triples)")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.text(0.5, -0.18,
            "no submission ≡ every localization/RCA metric is −1 in the row "
            "(the runner's marker that the agent never emitted a parseable submit() call)",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=8, style="italic", color="#555")
    fig.savefig(FIGS / "fig05_no_submission_rate.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig05_no_submission_rate.png'}")


def fig06_topology_scaling():
    """Two-panel S/M/L scaling: overall judge + total tokens (input+output). Horizontal layout for full-width (figure*) rendering."""
    sizes = ["s", "m", "l"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    panel_specs = [
        ("llm_judge_overall_score", "(a) Overall judge score", "score (1-5)", "{:.2f}"),
        ("total_tokens", "(b) Overall token budget (input + output)", "total tokens (thousands)", "{:.0f}"),
    ]
    # Add a derived column for total tokens (input + output)
    if "total_tokens" not in unified.columns:
        unified["total_tokens"] = unified["in_tokens"].fillna(0) + unified["out_tokens"].fillna(0)
    for ax, (col, title, ylabel, fmt) in zip(axes, panel_specs):
        x = np.arange(len(sizes))
        width = 0.26
        all_means = []
        for i, a in enumerate(AGENT_ORDER):
            ys, errs = [], []
            for sz in sizes:
                d = unified[(unified["agent"] == a) & (unified["scenario_topo_size"] == sz)][col].dropna()
                ys.append(d.mean() if len(d) else 0)
                errs.append((d.std() / np.sqrt(len(d))) if len(d) > 1 else 0)
            if col == "total_tokens":
                ys = [y / 1000 for y in ys]
                errs = [e / 1000 for e in errs]
            xpos = x + (i - 1) * width
            ax.bar(xpos, ys, width=width, yerr=errs,
                   color=AGENT_COLOR[a], capsize=3,
                   edgecolor="black", linewidth=0.5,
                   label=a, error_kw={"alpha": 0.7})
            for xi, yi in zip(xpos, ys):
                ax.text(xi, yi, fmt.format(yi),
                        ha="center", va="bottom",
                        fontsize=10, fontweight="bold")
            all_means.extend(ys)
        ax.set_xticks(x)
        ax.set_xticklabels(["small (s)", "medium (m)", "large (l)"], fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=13)
        ax.tick_params(axis='y', labelsize=11)
        ax.grid(axis="y", linestyle=":", alpha=0.4)
        if col == "llm_judge_overall_score":
            ax.set_ylim(min(all_means) * 0.95, max(all_means) * 1.10)
        else:
            ax.set_ylim(0, max(all_means) * 1.18)
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=AGENT_COLOR[a]) for a in AGENT_ORDER]
    legend_labels = ["ReAct (GPT-5, original NIKA baseline)",
                     "CC-Baseline (Claude Code, no SADE)",
                     "SADE (Claude Code + SADE workflow)"]
    fig.legend(legend_handles, legend_labels, loc="lower center", ncol=3,
               frameon=False, bbox_to_anchor=(0.5, -0.04), fontsize=11)
    fig.savefig(FIGS / "fig06_topology_scaling.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"  wrote {FIGS/'fig06_topology_scaling.png'}")


def fig07_nika_limits():
    """NIKA injector limits: SADE on manual_injection vs train_obs.

    Also persists ``data/nika_failure_breakdown.csv`` --- the merged
    record of (manual_injection, train_obs) outcomes plus the
    deployment-skip rows from ``benchmark_skips.csv``. The discussion
    section's NIKA-injector audit table reads from this CSV.
    """
    nika = []
    for label, p in [("manual_injection", NIKA_SOURCES["manual_injection"]),
                     ("train_obs",        NIKA_SOURCES["train_obs"])]:
        if not p.is_file():
            continue
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    fo = float(r.get("llm_judge_final_outcome_score", "0") or 0)
                except ValueError:
                    fo = 0
                nika.append({
                    "source": label,
                    "problem": r.get("root_cause_name", "?"),
                    "final_outcome": fo,
                })
    nika_df = pd.DataFrame(nika)

    # Deployment skips: benchmark cases where the test-set runner
    # could not deploy the lab. Captured for the audit table only;
    # not plotted.
    deploy = []
    if NIKA_SOURCES["skips_test"].is_file():
        with NIKA_SOURCES["skips_test"].open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                deploy.append({
                    "source": "deployment_skip",
                    "problem": r.get("problem", "?"),
                    "exception_type": r.get("exception_type", "?"),
                })

    # Only persist the breakdown when we actually have NIKA-set rows.
    # Otherwise we would overwrite a previously committed 80-row CSV
    # with a 2-row deployment-skip-only file on machines that don't have
    # NIKA_LIMITS_DIR pointing at the manual_injection / train_obs runs.
    if not nika_df.empty:
        breakdown = pd.concat(
            [
                nika_df.assign(category="nika_set"),
                pd.DataFrame(deploy).assign(category="deployment_skip"),
            ],
            ignore_index=True,
        )
        breakdown.to_csv(DATA / "nika_failure_breakdown.csv", index=False)
        print(f"  wrote {DATA/'nika_failure_breakdown.csv'}")
    else:
        print("  (skipping nika_failure_breakdown.csv: NIKA_LIMITS_DIR not set)")
        print("  (skipping fig07 plot: NIKA-limits CSVs missing)")
        return

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2),
                             gridspec_kw={"width_ratios": [1.0, 1.4]})

    # ---- Panel (a) ----
    ax = axes[0]
    cats = ["correct (>=4)", "partial (2-3)", "wrong (<=1)"]
    cat_colors = ["#4c8b3d", "#ddb135", "#b8473a"]
    sources = ["manual_injection", "train_obs"]
    n_per_source = {s: (nika_df["source"] == s).sum() for s in sources}
    bottom = np.zeros(len(sources))
    for k, cat in enumerate(cats):
        vals = []
        for s in sources:
            sub = nika_df[nika_df["source"] == s]
            if cat == "correct (>=4)":
                m = (sub["final_outcome"] >= 4).sum()
            elif cat == "partial (2-3)":
                m = ((sub["final_outcome"] >= 2) & (sub["final_outcome"] < 4)).sum()
            else:
                m = (sub["final_outcome"] < 2).sum()
            n = max(len(sub), 1)
            vals.append(m / n * 100)
        ax.bar(sources, vals, bottom=bottom, color=cat_colors[k],
               edgecolor="black", linewidth=0.5, label=cat, width=0.6)
        for xi, v, b0 in zip(range(len(sources)), vals, bottom):
            if v >= 5:
                ax.text(xi, b0 + v / 2, f"{v:.0f}%", ha="center", va="center",
                        color="white", fontsize=11, fontweight="bold")
        bottom += vals
    ax.set_ylabel("% of sessions (SADE agent)")
    ax.set_xticks(range(len(sources)))
    ax.set_xticklabels([
        f"manual_injection\n(clean, n={n_per_source['manual_injection']})",
        f"train_obs\n(ambiguous, n={n_per_source['train_obs']})",
    ], fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_title("(a) Outcome split per NIKA regime")
    ax.legend(frameon=False, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.13), ncol=3)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    # ---- Panel (b) ----
    ax = axes[1]
    train_obs = nika_df[nika_df["source"] == "train_obs"]["final_outcome"].astype(int)
    score_counts = train_obs.value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
    bar_colors = ["#b8473a", "#b8473a", "#ddb135", "#4c8b3d", "#4c8b3d"]
    ax.bar(score_counts.index, score_counts.values, color=bar_colors,
           edgecolor="black", linewidth=0.5, width=0.7)
    for x, v in zip(score_counts.index, score_counts.values):
        if v > 0:
            ax.text(x, v + 0.4, str(int(v)), ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xlabel("LLM-judge final-outcome score")
    ax.set_ylabel("# of train_obs sessions")
    ax.set_ylim(0, max(score_counts.values) * 1.18)
    ax.set_title(f"(b) train_obs final-outcome distribution is bimodal (n={len(train_obs)})")
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    fig.suptitle("NIKA injector limits: agent fixed (SADE), regime varied",
                 fontsize=11, y=1.02)
    fig.savefig(FIGS / "fig07_nika_limits.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig07_nika_limits.png'}")


def fig08_time_taken():
    """Mean wall-clock per session per agent."""
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    means, errs = [], []
    for a in AGENT_ORDER:
        d = unified[unified["agent"] == a]["time_taken"].dropna()
        means.append(d.mean())
        errs.append(d.std() / np.sqrt(len(d)) if len(d) else 0)
    x = np.arange(len(AGENT_ORDER))
    colors = [AGENT_COLOR[a] for a in AGENT_ORDER]
    ax.bar(x, means, yerr=errs, color=colors, capsize=3,
           edgecolor="black", linewidth=0.5, error_kw={"alpha": 0.7}, width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=10)
    ax.set_ylabel("time_taken (seconds)")
    ax.set_title(f"Mean time_taken per session (test, n={len(common)} matched triples; error bars = SEM)")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for xi, m in zip(x, means):
        ax.text(xi, m + max(means) * 0.03, f"{m:.1f} s",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(means) * 1.20)
    fig.savefig(FIGS / "fig08_time_taken.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig08_time_taken.png'}")


def fig09_tool_errors():
    """Tool-error rate using the hybrid source per agent.

    ReAct  -> CSV `tool_errors` column (LangGraph error-handler counts).
    CC/SADE -> log-counted `is_error: true` from tool_end events
               (the runner's CSV column reports 0 — Claude Code SDK's
               is_error flag isn't wired into CSV writing).
    """
    err_path = DATA / "tool_errors_from_logs.csv"
    if not err_path.is_file():
        print(f"  (skipping fig09: {err_path.name} missing)")
        return
    err_df = pd.read_csv(err_path)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
    x = np.arange(len(AGENT_ORDER))
    colors = [AGENT_COLOR[a] for a in AGENT_ORDER]

    def errors_per_agent(a: str) -> tuple[int, int, int]:
        if a == "ReAct (GPT-5)":
            sub = unified[unified["agent"] == a]
            te = pd.to_numeric(sub["tool_errors"], errors="coerce").fillna(0).astype(int)
            return int(te.sum()), int((te > 0).sum()), int(sub["tool_calls"].sum())
        sub = err_df[err_df["agent"] == a]
        return (int(sub["log_is_err"].clip(lower=0).sum()),
                int((sub["log_is_err"] > 0).sum()),
                int(unified[unified["agent"] == a]["tool_calls"].sum()))

    # ---- Panel (a) ----
    ax = axes[0]
    pcts, ks, ns = [], [], []
    for a in AGENT_ORDER:
        _, k, _ = errors_per_agent(a)
        n = (err_df["agent"] == a).sum() if a != "ReAct (GPT-5)" else (unified["agent"] == a).sum()
        ks.append(k); ns.append(n)
        pcts.append((k / n * 100) if n else 0)
    ax.bar(x, pcts, color=colors, edgecolor="black", linewidth=0.5, width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=10)
    ax.set_ylabel("% of sessions with ≥1 tool error")
    ax.set_title("(a) Sessions with any tool error")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for xi, p, k, n in zip(x, pcts, ks, ns):
        ax.text(xi, p + max(pcts) * 0.04,
                f"{p:.1f}%\n({k}/{n})",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(pcts) * 1.30 if max(pcts) else 1)

    # ---- Panel (b) ----
    ax = axes[1]
    rates, totals_e, totals_c = [], [], []
    for a in AGENT_ORDER:
        total_err, _, total_calls = errors_per_agent(a)
        totals_e.append(total_err); totals_c.append(total_calls)
        rates.append((total_err / total_calls * 100) if total_calls else 0)
    ax.bar(x, rates, color=colors, edgecolor="black", linewidth=0.5, width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=10)
    ax.set_ylabel("error rate (errors / total tool_calls)")
    ax.set_title("(b) Per-tool-call error rate")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for xi, r, e, c in zip(x, rates, totals_e, totals_c):
        ax.text(xi, r + max(rates) * 0.04 if max(rates) else 0.02,
                f"{r:.2f}%\n({e:,}/{c:,})",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(rates) * 1.30 if max(rates) else 1)

    fig.suptitle(f"Tool-error rate (test, n={len(common)} matched triples)",
                 fontsize=11, y=1.02)
    fig.text(0.5, -0.05,
             "Source per agent: ReAct from the runner's `tool_errors` CSV column "
             "(LangGraph error-handler counts); CC-Baseline and SADE from "
             "log-counted `is_error: true` events in tool_end (Claude Code SDK).",
             ha="center", fontsize=8.5, style="italic", color="#444")
    fig.savefig(FIGS / "fig09_tool_errors.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig09_tool_errors.png'}")


def fig10_tool_calls():
    """Tool-call efficiency: mean per session and per correct submission."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))

    # ---- Panel (a) ----
    ax = axes[0]
    means, errs = [], []
    for a in AGENT_ORDER:
        d = unified[unified["agent"] == a]["tool_calls"].dropna()
        means.append(d.mean())
        errs.append(d.std() / np.sqrt(len(d)) if len(d) else 0)
    x = np.arange(len(AGENT_ORDER))
    colors = [AGENT_COLOR[a] for a in AGENT_ORDER]
    ax.bar(x, means, yerr=errs, color=colors, capsize=3,
           edgecolor="black", linewidth=0.5, error_kw={"alpha": 0.7}, width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=9)
    ax.set_ylabel("tool_calls (per session)")
    ax.set_title("(a) Mean tool_calls per session")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for xi, m in zip(x, means):
        ax.text(xi, m + max(means) * 0.04, f"{m:.1f}",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(means) * 1.25)

    # ---- Panel (b) ----
    ax = axes[1]
    ratios = []
    annotation_parts = []
    for a in AGENT_ORDER:
        d = unified[unified["agent"] == a]
        total_calls = int(d["tool_calls"].sum())
        correct = int((d["llm_judge_final_outcome_score"] >= 4).sum())
        r = total_calls / correct if correct else float("nan")
        ratios.append(r)
        annotation_parts.append((total_calls, correct))
    ax.bar(x, ratios, color=colors, edgecolor="black", linewidth=0.5, width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(["ReAct\n(GPT-5)", "CC-Base\n(Sonnet)", "SADE\n(Sonnet)"], fontsize=9)
    ax.set_ylabel("tool_calls per correct submission")
    ax.set_title("(b) tool_calls / correct submission   [lower = better]")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for xi, r, (tc, c) in zip(x, ratios, annotation_parts):
        ax.text(xi, r + max(ratios) * 0.04,
                f"{r:.1f}\n({tc:,}/{c})",
                ha="center", fontsize=9, fontweight="bold")
    ax.set_ylim(0, max(ratios) * 1.30)

    fig.suptitle(f"Tool-call efficiency (test, n={len(common)} matched triples)",
                 fontsize=11, y=1.02)
    fig.savefig(FIGS / "fig10_tool_calls.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGS/'fig10_tool_calls.png'}")


print("Rendering figures:")
fig01_headline()
fig02_per_family()
fig02_per_category()
fig03_efficiency()
fig04_token_budget()
fig05_no_submission_rate()
fig06_topology_scaling()
fig07_nika_limits()
fig08_time_taken()
fig09_tool_errors()
fig10_tool_calls()
print()

print(f"Done. Figures in: {FIGS}")
