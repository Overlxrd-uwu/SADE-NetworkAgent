"""Sample sessions per agent, recount tool_start events from logs,
and compare against the CSV's tool_calls column."""
import json
import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ROOTS = {
    "ReAct (GPT-5)": ROOT / "Research_results/results_ReAct_GPT5/results",
    "CC-Baseline":   ROOT / "results_ClaudeB",
    "SADE":          ROOT / "results_sade",
}

df = pd.read_csv(ROOT / "Research_results/data/unified_test_3way.csv",
                 dtype={"session_id": str})
df["session_id"] = df["session_id"].astype(str).str.zfill(10)

random.seed(7)
checked = 0
disagreements = 0
header = f"{'agent':<14} {'sid':<12} {'csv':>4} {'log':>4} {'diff':>4}"
print(header)
print("-" * len(header))
for a, root in ROOTS.items():
    sub = df[df["agent"] == a].sample(n=10, random_state=7)
    for _, r in sub.iterrows():
        log = root / r["root_cause_name"] / r["session_id"] / "conversation_diagnosis_agent.log"
        if not log.is_file():
            continue
        n_log = 0
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
                    if evt.get("event") == "tool_start":
                        n_log += 1
        except OSError:
            continue
        n_csv = int(r["tool_calls"])
        diff = n_log - n_csv
        checked += 1
        if diff != 0:
            disagreements += 1
        print(f"{a:<14} {r['session_id']:<12} {n_csv:>4} {n_log:>4} {diff:>+4}")

print()
print(f"checked: {checked} | disagreements: {disagreements}")
