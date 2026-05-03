# Research_results

LCN-paper analysis pack comparing **SADE** (Claude-Code with the SADE workflow) against two baselines on the NIKA network-fault diagnosis benchmark.

All three agents are evaluated on the **held-out test set** (`benchmark/benchmark_test.csv`) and matched on (problem, scenario, topo_size) triples. Comparison is restricted to the 523 triples that all three agents successfully evaluated.

## Three test-set agents

| Agent | Source | Framework / Model | Workflow scaffolding |
|---|---|---|---|
| **ReAct (GPT-5)** | `Research_results/results_ReAct_GPT5/results/` | LangGraph ReAct, `gpt-5-mini` (NIKA's original baseline) | None — minimal prompt only |
| **CC-Baseline** | `results_ClaudeB/` | Claude Code (Sonnet 4.6) | None — minimal prompt only |
| **SADE** | `results_sade/` | Claude Code (Sonnet 4.6) | Phase gates, fault-family skills, `CLAUDE.md` fault-routing index |

All three see the same MCP tool surface (`task_mcp_server.list_avail_problems`, `submit`, the Kathara base/FRR/BMv2 servers, etc.) and the same problem suite. They differ only in framework and the SADE-side workflow scaffolding.

## NIKA injector-limit sources (purpose-different, both SADE-driven)

These are *not* part of the agent comparison. They were both run with SADE and surface NIKA's own benchmark-side limitations (cases the injector does not cleanly produce, or where the planted symptom is ambiguous to a thorough agent):

- `nika-claude/results_manual_injection/` (39 rows)
- `nika-claude/results_train_obs/` (39 rows)
- `results_sade/0_summary/benchmark_skips.csv` (deployment-time injector failures)

These feed into Figure 7 / `nika_failure_breakdown.csv` only.

## Headline numbers (test set, 523 matched triples)

| Metric | ReAct (GPT-5) | CC-Baseline | **SADE** |
|---|---:|---:|---:|
| Overall judge (1–5) | 3.81 | 3.93 | **4.32** |
| Final outcome (1–5) | 3.21 | 3.30 | **4.01** |
| Detection accuracy | 0.69 | 0.67 | **0.85** |
| Localization F1 | 0.61 | 0.80 | **0.81** |
| RCA F1 | 0.44 | 0.65 | **0.80** |
| Mean input tokens | 67k | 236k | 395k |
| Mean output tokens | 10.9k | 9.5k | 12.9k |
| Mean wall-clock (s) | 227 | 217 | 261 |

**Bold** = best. SADE wins every correctness metric. The token-cost ladder is exactly inverted: ReAct cheapest (67k) but worst on RCA (0.44); SADE most expensive (395k) but strongest correctness across the board.

## Statistical significance (paired Wilcoxon signed-rank)

Across all three matched-pair comparisons (SADE vs CC, SADE vs ReAct, CC vs ReAct):

| Comparison | Overall | Final outcome | Localization F1 | RCA F1 |
|---|---:|---:|---:|---:|
| SADE vs CC-Baseline | p < 1e-4 | p < 1e-4 | p < 1e-4 | p < 1e-4 |
| SADE vs ReAct (GPT-5) | p < 1e-4 | p < 1e-4 | p < 1e-4 | p < 1e-4 |
| CC-Baseline vs ReAct | **p = 0.026** | p = 0.17 (n.s.) | p = 0.10 (n.s.) | **p = 0.010** |

Three useful claims fall out:
1. **SADE > both baselines** on every correctness metric (p < 1e-4).
2. **CC-Baseline is significantly better than ReAct on RCA F1** (p = 0.010) — the framework matters even without SADE scaffolding.
3. **SADE's token cost is significantly higher** than both baselines (p < 1e-4 in both directions). Wall-clock time is significantly slower than CC (p < 1e-4) but not significantly different from ReAct (p = 0.42).

Full table in `tables/table_significance.csv`.

## Figures (300 DPI, IEEE-styled, in `figures/`)

| File | Caption / Paper section |
|---|---|
| `fig01_headline.png` | 5-panel headline metrics with error bars (SEM). Goes in **Sec 5.1 Headline results**. |
| `fig02_per_family.png` | Per fault-family overall-score heatmap (3 columns × ~50 families). Goes in **Sec 5.2 Per-fault-family analysis**. Single most-impactful figure for the paper. |
| `fig03_efficiency.png` | Cost-vs-correctness scatter: input tokens vs overall judge score. Goes in **Sec 5.3 Cost vs correctness**. Pareto-style argument: SADE's cluster sits up-and-right. |
| `fig04_token_budget.png` | Per-session input-token boxplot (3 agents). Goes in **Sec 5.3** alongside fig03. |
| `fig05_outcome_distribution.png` | Stacked bars of correct (≥4) / partial (2–3) / wrong (≤1) by agent. Goes in **Sec 5.5 Failure modes**. |
| `fig06_topology_scaling.png` | Test-set s/m/l scaling for overall score and tokens. Goes in **Sec 5.4 Scaling**. |
| `fig07_nika_limits.png` | Two-panel: (a) injector deployment failures by exception class, (b) where SADE still fails on `manual_injection`/`train_obs` cases. Goes in **Sec 6 Limitations**. |

## Tables (`tables/`)

- `table_headline_metrics.csv` — paper Table 1 (per-agent mean / std / median for every reported metric).
- `table_per_family.csv` — per-(family × agent) means, tabular form of fig02.
- `table_topology_scaling.csv` — per-(topo_size × agent) breakdown for fig06.
- `table_significance.csv` — paired Wilcoxon results: median-A, median-B, median-diff, p-value for every (metric × agent-pair).

## Unified data (`data/`)

- `unified_test_3way.csv` — all three test-set agents on the 523 matched triples (one row per agent×triple). The single source of truth for every figure and table.
- `nika_failure_breakdown.csv` — exception classes from the deployment-skip log plus misclassified cases from `manual_injection` / `train_obs`.

Rebuild any time:
```bash
python Research_results/build_research_results.py
```

Idempotent — reads the three test CSVs at the top of the script, regenerates everything else.

## Caveats and known data quirks

1. **`localization_f1 = -1` for some P4 cases.** When a problem has no canonical device-set mapping (e.g. some P4 fault families with `topo_size = -`), the runner records −1 and only the LLM judge is authoritative. The F1 means in fig01 / table_headline are computed over rows where F1 ≥ 0; the LLM-judge metrics include those rows.
2. **ReAct's localization F1 (0.61) is significantly lower than CC-Baseline's (0.80)** despite both using `list_avail_problems()` and the same submit signature. The gap is in *device localization* — ReAct often submits subsets or wrong devices; the LLM-judge final outcome (3.21 vs 3.30) is much closer.
3. **`no_submission_rate` is heuristic.** Computed as the fraction with `localization_precision = recall = 0` AND `final_outcome ≤ 1`, approximating "agent submitted nothing useful." Not equal to literal empty submission.
4. **ReAct sample size: 524 rows / 523 unique triples** (one duplicate). After 3-way matching with CC and SADE (530 each, 530 unique), the common set is **523 triples**. The 7 triples in CC/SADE without a ReAct row are excluded from the 3-way comparison.
5. **Token cost cardinality.** ReAct's mean input (67k) is much smaller than the train-set ReAct numbers we previously had (114k). The test-set ReAct sessions are evidently shorter; the median/mean reported in this pack reflects the test-set runs only.
6. **Wall-clock comparison is approximate.** Time depends on machine load and concurrent runs; treat the means as ballpark, not as precise efficiency claims.

## Suggested LCN-paper narrative

- **Sec 4 Methodology**: cite this README for matched-pair construction; reference the agent-vs-baseline definitions above.
- **Sec 5.1 Headline**: insert `fig01_headline.png` + `table_headline_metrics.csv`. Cite Wilcoxon p-values from `table_significance.csv`.
- **Sec 5.2 Per fault family**: insert `fig02_per_family.png`. Discuss the green-dominated SADE column; call out the small set of families that resist all agents (`mac_address_conflict`, `host_incorrect_dns`, `sender_resource_contention`).
- **Sec 5.3 Cost vs correctness**: insert `fig03_efficiency.png` + `fig04_token_budget.png`. Argue: SADE costs ~1.7× CC-Baseline and ~6× ReAct in input tokens, but the relative correctness gain (overall +10%, RCA F1 +23–82%) clears the cost premium.
- **Sec 5.4 Scaling**: insert `fig06_topology_scaling.png`. SADE's correctness advantage holds across topology sizes; tokens scale roughly linearly.
- **Sec 5.5 Failure modes**: insert `fig05_outcome_distribution.png`. SADE pushes the bulk of sessions into the "correct" bucket; ReAct has the largest "wrong" share.
- **Sec 6 Limitations**: insert `fig07_nika_limits.png` + cite `nika_failure_breakdown.csv`. Use `manual_injection` / `train_obs` results to argue that some apparent agent failures are NIKA-side ambiguities, not workflow failures.

## Token augmentation provenance

All five contributing CSVs were token-augmented by parsing the last `llm_end` event in each session's `conversation_diagnosis_agent.log`. The reusable script `scripts/augment_generic.py` falls back from the SADE-style `tokens.total_input_tokens` to the raw SDK `usage.input_tokens + cache_creation_input_tokens + cache_read_input_tokens` so it works on either log shape.
