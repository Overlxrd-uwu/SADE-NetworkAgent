# Accuracy comparison (detection / localization / RCA)

Not for paper -- exploratory only. Localization and RCA accuracy are set-level confusion-matrix scores; we show two columns per metric to make the no-submission treatment explicit (`-1` is the runner's no-submit marker).

n = 523 matched test triples per agent.

| Agent | n_no_sub | Detection | Loc acc (no-sub=0) | Loc acc (drop no-sub) | RCA acc (no-sub=0) | RCA acc (drop no-sub) |
|---|---:|---:|---:|---:|---:|---:|
| ReAct (GPT-5) | 46 | 0.685 | 0.589 | 0.646 | 0.446 | 0.488 |
| CC-Baseline | 80 | 0.667 | 0.693 | 0.818 | 0.556 | 0.657 |
| SADE | 22 | 0.853 | 0.793 | 0.827 | 0.780 | 0.814 |

**Why the paper uses F1, not these accuracy values.** For localization and RCA the device/label space is heavily imbalanced (1-3 faulty devices in 11-101-node topologies). Confusion-matrix accuracy on such a set has a no-skill ceiling near 95-99%, which an empty submission can hit by exclusion alone -- the values above are noticeably squashed into the high-accuracy band even when the agent is wrong, while F1 collapses to 0 in those cases.