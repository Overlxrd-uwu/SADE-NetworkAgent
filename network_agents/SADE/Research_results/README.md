# Research_results

Analysis pack for the SADE evaluation: per-agent run CSVs, the unified
matched-set CSV, log-scanned tool-error counts, and the rendered figures
and tables that read from them. Everything in this directory is
regenerable from `build_research_results.py` plus the per-agent run
artifacts in `results_{ReAct_GPT5, ClaudeB, sade}/`.

## Agents under comparison

All three agents run on the same 4-step NIKA pipeline (`step1_net_env_start`
→ `step2_failure_inject` → `step3_agent_run` → `step4_result_eval`) over
identical (problem, scenario, topo_size) triples. They differ only in the
agent framework and the workflow scaffolding.

| Agent | Source dir | Framework | Backbone | Workflow scaffolding |
|---|---|---|---|---|
| **ReAct (GPT-5)** | `results_ReAct_GPT5/results/` | LangGraph ReAct | `gpt-5` | minimal prompt only |
| **CC-Baseline** | `results_ClaudeB/` | Claude Code SDK | Claude Sonnet 4.6 | minimal prompt only |
| **SADE** | `results_sade/` | Claude Code SDK | Claude Sonnet 4.6 | phase gates + 15-skill library + diagnosis manual |

The `results_*/0_summary/evaluation_summary.csv` file in each agent dir is
the single per-row record produced by `step4_result_eval.py`. The matched
test slice is the intersection of those three CSVs on (problem, scenario,
topo_size).

## NIKA-injector audit sources (separate purpose)

These are *not* part of the agent comparison — both runs use SADE. They
exist to characterise NIKA's fault-injection layer itself:

- `manual_injection` (39 rows) — runs under a verified-injection harness
  that confirms the fault is actually installed before scoring.
- `train_obs` (39 rows) — runs under NIKA's stock injection on the same
  fault families.
- `benchmark_skips.csv` (deployment-time injector failures) — captured
  per agent in `results_*/0_summary/benchmark_skips.csv`.

These three sources feed `data/nika_failure_breakdown.csv` and Figure 7;
the rendered audit table referenced from the discussion section reads
from there.

## Layout

```
Research_results/
├── data/
│   ├── unified_test_3way.csv         # 3-way matched test slice (523 × 3 = 1569 rows)
│   ├── tool_errors_from_logs.csv     # log-scanned `is_error: true` counts per session
│   └── nika_failure_breakdown.csv    # NIKA-injector audit (manual + train_obs + skips)
├── figures/                           # 11 PNGs + data_provenance.{md,pdf}
├── tables/                            # paper Table 1 + per-family / topology / time-efficiency (csv + md)
├── examples/                          # SADE-wins case study + accuracy sidecar
├── results_ClaudeB/, results_sade/, results_ReAct_GPT5/   # per-agent run CSVs (input)
├── build_research_results.py         # one-shot regenerator for figures, tables, and data/*.csv
├── build_examples.py                 # writes examples/sade_wins.md
└── _verify_tool_calls.py, _verify_tool_errors.py    # sample audits (stdout only)
```

## How everything regenerates

```bash
pip install matplotlib numpy pandas
python Research_results/build_research_results.py
```

The script runs three steps:

1. Load the three per-agent `evaluation_summary.csv` files, intersect on
   (problem, scenario, topo_size), persist `data/unified_test_3way.csv`.
2. Walk every session's `conversation_diagnosis_agent.log`, count
   `tool_end` events with `is_error: true`, persist
   `data/tool_errors_from_logs.csv`. Required by fig09 because the runner
   does not record tool-error counts in the CSV for Claude-Code agents.
3. Render 11 PNGs into `figures/` and 4 paper tables (csv + md) into
   `tables/`. Figure 7 also persists `data/nika_failure_breakdown.csv`
   when `NIKA_LIMITS_DIR` is set (see below); without it, the existing
   committed CSV is left untouched.

`build_examples.py` (run separately) regenerates `examples/sade_wins.md`,
the case-by-case "where SADE beats both baselines" walkthrough.

## NIKA limits dataset is not in the repo

`results_manual_injection/` and `results_train_obs/` are not committed.
To regenerate `nika_failure_breakdown.csv` and the Figure 7 plot from
scratch, point at the directory containing them:

```bash
NIKA_LIMITS_DIR=/path/to/dir/with/results_{manual_injection,train_obs} \
    python Research_results/build_research_results.py
```

Without the env var, the build skips Figure 7's plot and the breakdown
write — the committed CSV stays in place so reviewers without the audit
data still see the right table from the discussion.

## Files

### `figures/` — 11 PNGs

| File | What it shows | Read from |
|---|---|---|
| `fig01_headline.png` | Three-panel headline (Overall judge, RCA F1, Detection accuracy) per agent | `unified_test_3way.csv` |
| `fig02_per_family.png` | Per (fault family × agent) overall-score heatmap | `unified_test_3way.csv` |
| `fig02_per_category.png` | Per NIKA root-cause category (6 buckets) bar chart | `unified_test_3way.csv` |
| `fig03_efficiency.png` | Cost-vs-correctness scatter: input tokens vs overall judge | `unified_test_3way.csv` |
| `fig04_token_budget.png` | Per-session input-token boxplot | `unified_test_3way.csv` |
| `fig05_no_submission_rate.png` | % of sessions where every loc/RCA metric is −1 | `unified_test_3way.csv` |
| `fig06_topology_scaling.png` | s/m/l overall-score and input-token by topology size | `unified_test_3way.csv` |
| `fig07_nika_limits.png` | NIKA injector regimes (verified vs stock) outcome split | `nika_failure_breakdown.csv` |
| `fig08_time_taken.png` | Mean wall-clock per agent | `unified_test_3way.csv` |
| `fig09_tool_errors.png` | Per-session and per-tool-call error rate (hybrid source) | `tool_errors_from_logs.csv` + `unified_test_3way.csv` |
| `fig10_tool_calls.png` | Mean tool calls per session and per correct submission | `unified_test_3way.csv` |

### `tables/` — paper tables (csv + md)

| File | Source |
|---|---|
| `table_headline_metrics.{csv,md}` | per-agent overall, final, detection, F1s, tokens, time, no-submission |
| `table_per_family.{csv,md}` | per-(fault family × agent) overall and final scores |
| `table_topology_scaling.{csv,md}` | per-(topology size × agent) overall, final, tokens, time |
| `table_time_efficiency.{csv,md}` | mean / median time, tokens-per-correct, % correct |

### `data/` — all reproducible

Each CSV has a documented generator in `build_research_results.py` (see
"How everything regenerates" above). No orphan files.

### `examples/`

- `sade_wins.md` — narrative walk-through of cases where SADE submits the
  canonical label and both baselines fail. Regenerated by `build_examples.py`.
- `accuracy_panels.png`, `accuracy_table.{csv,md}` — accuracy-view sidecar
  preserved from earlier analysis (no live regenerator).

## Caveats and known data quirks

1. **`localization_f1 = -1` markers.** Sessions where the runner could not
   score a submission (no parseable `submit()`, or no canonical
   device-set mapping for some P4 fault families with `topo_size = -`)
   are recorded with all loc/RCA metrics at −1. The F1 columns in the
   paper tables clip these to 0 (failing to submit is a real outcome,
   not missing data); the LLM-judge columns include them.
2. **`no_submission_rate` heuristic.** Defined as the fraction of sessions
   where every loc/RCA metric is −1. Approximates "agent never produced a
   parseable submit", not literal empty submission.
3. **Sample-size mismatch.** ReAct has 524 rows / 523 unique triples (one
   duplicate); CC-Baseline and SADE have 530 each. The 3-way matched
   intersection is 523 triples — the 7 in CC/SADE without a matching
   ReAct row are excluded from headline metrics.
4. **Tool-error counts are hybrid.** The runner's `tool_errors` CSV column
   is reliable for ReAct (LangGraph captures errors via its handler) but
   reports 0 for both Claude agents (the SDK's `is_error` flag is not
   wired into the CSV writer). fig09 reads ReAct from the CSV column and
   the two Claude agents from `tool_errors_from_logs.csv`. See the figure
   caption for the source per agent.
5. **Wall-clock comparison is approximate.** Runtimes depend on machine
   load and concurrent labs. Treat means as ballpark.
