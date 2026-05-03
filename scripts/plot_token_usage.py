"""Generate short token-usage visualizations for SADE evaluation_summary.csv.

Outputs four PNGs to doc/image/:
  - token_distribution.png      (histogram of in_tokens and out_tokens)
  - tokens_by_topo_size.png     (s/m/l boxplot)
  - tokens_by_category.png      (per-fault-family mean ± std, sorted)
  - tokens_vs_score.png         (in_tokens vs overall judge score scatter)
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results_sade" / "0_summary" / "evaluation_summary.csv"
OUT = ROOT / "doc" / "image"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

df = pd.read_csv(CSV)
df["in_tokens"] = pd.to_numeric(df["in_tokens"], errors="coerce")
df["out_tokens"] = pd.to_numeric(df["out_tokens"], errors="coerce")
df["llm_judge_overall_score"] = pd.to_numeric(df["llm_judge_overall_score"], errors="coerce")
df = df.dropna(subset=["in_tokens", "out_tokens"])

print(f"Plotting {len(df)} sessions from {CSV.name}")
print(f"  in_tokens : median={df['in_tokens'].median():,.0f}  max={df['in_tokens'].max():,.0f}")
print(f"  out_tokens: median={df['out_tokens'].median():,.0f}  max={df['out_tokens'].max():,.0f}")


# 1. Token distribution histogram (input + output stacked side-by-side)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
axes[0].hist(df["in_tokens"] / 1000, bins=40, color="#3a6fb0", edgecolor="white")
axes[0].axvline(df["in_tokens"].median() / 1000, color="firebrick", linestyle="--", linewidth=1, label=f"median {df['in_tokens'].median()/1000:.0f}k")
axes[0].set_xlabel("input tokens (thousands)")
axes[0].set_ylabel("session count")
axes[0].set_title(f"Input token distribution  (n={len(df)})")
axes[0].legend(frameon=False, fontsize=9)

axes[1].hist(df["out_tokens"] / 1000, bins=40, color="#c47236", edgecolor="white")
axes[1].axvline(df["out_tokens"].median() / 1000, color="firebrick", linestyle="--", linewidth=1, label=f"median {df['out_tokens'].median()/1000:.1f}k")
axes[1].set_xlabel("output tokens (thousands)")
axes[1].set_ylabel("session count")
axes[1].set_title("Output token distribution")
axes[1].legend(frameon=False, fontsize=9)
fig.suptitle("SADE token usage per session", fontsize=12, y=1.02)
fig.savefig(OUT / "token_distribution.png")
plt.close(fig)
print(f"  wrote {OUT/'token_distribution.png'}")


# 2. Tokens by topo size (s/m/l)
size_order = ["s", "m", "l", "-"]
sizes_present = [s for s in size_order if s in df["scenario_topo_size"].unique()]
data_in = [df[df["scenario_topo_size"] == s]["in_tokens"] / 1000 for s in sizes_present]
data_out = [df[df["scenario_topo_size"] == s]["out_tokens"] / 1000 for s in sizes_present]
labels = [f"{s} (n={len(d)})" for s, d in zip(sizes_present, data_in)]

fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
bp1 = axes[0].boxplot(data_in, tick_labels=labels, showfliers=False, patch_artist=True)
for box in bp1["boxes"]:
    box.set_facecolor("#3a6fb0")
    box.set_alpha(0.7)
axes[0].set_ylabel("input tokens (thousands)")
axes[0].set_title("Input tokens by topology size")

bp2 = axes[1].boxplot(data_out, tick_labels=labels, showfliers=False, patch_artist=True)
for box in bp2["boxes"]:
    box.set_facecolor("#c47236")
    box.set_alpha(0.7)
axes[1].set_ylabel("output tokens (thousands)")
axes[1].set_title("Output tokens by topology size")
fig.suptitle("Token usage scales with topology size", fontsize=12, y=1.02)
fig.savefig(OUT / "tokens_by_topo_size.png")
plt.close(fig)
print(f"  wrote {OUT/'tokens_by_topo_size.png'}")


# 3. Tokens by fault category (sorted by median input tokens)
agg = df.groupby("root_cause_name").agg(
    in_mean=("in_tokens", "mean"),
    in_std=("in_tokens", "std"),
    out_mean=("out_tokens", "mean"),
    n=("in_tokens", "count"),
).sort_values("in_mean", ascending=True)

fig, ax = plt.subplots(figsize=(8.5, max(6, len(agg) * 0.22)))
y = np.arange(len(agg))
ax.barh(y, agg["in_mean"] / 1000, xerr=agg["in_std"].fillna(0) / 1000,
        color="#3a6fb0", alpha=0.85, ecolor="#666", capsize=2,
        error_kw={"alpha": 0.4})
ax.set_yticks(y)
ax.set_yticklabels([f"{n}  (n={c})" for n, c in zip(agg.index, agg['n'])], fontsize=8)
ax.set_xlabel("mean input tokens (thousands) ± std")
ax.set_title(f"Mean input tokens per fault family  (sorted, {len(agg)} families)")
ax.grid(axis="x", linestyle=":", alpha=0.4)
fig.savefig(OUT / "tokens_by_category.png")
plt.close(fig)
print(f"  wrote {OUT/'tokens_by_category.png'}")


# 4. Cost vs correctness scatter
df_clean = df.dropna(subset=["llm_judge_overall_score"])
fig, ax = plt.subplots(figsize=(7.5, 4.5))
sc = ax.scatter(
    df_clean["in_tokens"] / 1000,
    df_clean["llm_judge_overall_score"]
    + np.random.uniform(-0.12, 0.12, size=len(df_clean)),  # jitter for visibility
    c=df_clean["out_tokens"] / 1000,
    cmap="viridis",
    s=18,
    alpha=0.7,
    edgecolor="none",
)
cb = plt.colorbar(sc, ax=ax)
cb.set_label("output tokens (thousands)")
ax.set_xlabel("input tokens (thousands)")
ax.set_ylabel("LLM-judge overall score (1–5, jittered)")
ax.set_title(f"Cost vs correctness  (n={len(df_clean)} sessions)")
ax.set_yticks([1, 2, 3, 4, 5])
ax.grid(linestyle=":", alpha=0.4)
fig.savefig(OUT / "tokens_vs_score.png")
plt.close(fig)
print(f"  wrote {OUT/'tokens_vs_score.png'}")
