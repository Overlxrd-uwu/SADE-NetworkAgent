# Table 1 — Headline metrics (test set, 523 matched triples)

All three agents evaluated on the same matched (problem, scenario, topo_size) triples. Bold = best per metric. Higher is better for correctness; lower is better for cost.

| Metric | ReAct (GPT-5) | CC-Baseline | SADE |
|---|---:|---:|---:|
| Overall judge (1–5) | 3.80 | 3.93 | **4.32** |
| Final outcome (1–5) | 3.21 | 3.30 | **4.01** |
| Detection accuracy | 0.685 | 0.667 | **0.853** |
| Localization F1 | 0.556 | 0.680 | **0.776** |
| RCA F1 | 0.398 | 0.552 | **0.767** |
| Mean input tokens | **66,718** | 235,914 | 394,846 |
| Median input tokens | **54,983** | 189,144 | 343,969 |
| Mean output tokens | 10,940 | **9,513** | 12,867 |
| Mean wall-clock (s) | 227.6 | **216.5** | 261.2 |
| Mean tool calls | 25.4 | 26.7 | 19.9 |
| No-submission rate | 8.8% | 15.3% | **4.2%** |

*n = 523 matched triples. No-submission rows (where the agent never produced a parseable submit() call — flagged as F1 = −1 by the runner) count as F1 = 0 in the localization and RCA F1 means: failing to submit is a real outcome, not a missing measurement.*
