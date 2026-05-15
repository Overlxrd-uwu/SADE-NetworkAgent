"""Trace tool errors from conversation logs to validate the CSV's tool_errors column.

For each agent, sample sessions and count:
  is_error_true  : tool_end events where evt.get('is_error') == True
  err_in_text    : tool_end events whose 'output' string starts with markers like
                   '[TIMEOUT]' or 'Machine ' or 'Error: ' (NIKA/Kathara error
                   conventions for non-exception failures).
"""
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

ERROR_PREFIXES = ("[TIMEOUT]", "Machine ", "Error:", "Traceback", "ERROR:")


def scan(log: Path):
    is_err_true = 0
    err_text = 0
    if not log.is_file():
        return None
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
                if evt.get("event") == "tool_end":
                    if evt.get("is_error") is True:
                        is_err_true += 1
                    out = str(evt.get("output", ""))
                    if any(out.startswith(p) for p in ERROR_PREFIXES):
                        err_text += 1
    except OSError:
        return None
    return {"is_err_true": is_err_true, "err_text": err_text}


df = pd.read_csv(ROOT / "Research_results/data/unified_test_3way.csv",
                 dtype={"session_id": str})
df["session_id"] = df["session_id"].astype(str).str.zfill(10)
df["tool_errors"] = pd.to_numeric(df["tool_errors"], errors="coerce")

random.seed(7)
print(f"{'agent':<14} {'sid':<12} {'csv':>4} {'is_err':>6} {'txt':>4} {'agree?':>8}")
print("-" * 60)
totals = {a: {"csv_sum": 0, "log_is_err": 0, "log_text": 0, "checked": 0}
          for a in ROOTS}
for a, root in ROOTS.items():
    sub = df[df["agent"] == a].sample(n=15, random_state=7)
    for _, r in sub.iterrows():
        log = root / r["root_cause_name"] / r["session_id"] / "conversation_diagnosis_agent.log"
        s = scan(log)
        if s is None:
            continue
        n_csv = int(r["tool_errors"])
        is_err = s["is_err_true"]
        et = s["err_text"]
        totals[a]["csv_sum"] += n_csv
        totals[a]["log_is_err"] += is_err
        totals[a]["log_text"] += et
        totals[a]["checked"] += 1
        agree = "OK" if n_csv == is_err else f"diff{is_err-n_csv:+d}"
        print(f"{a:<14} {r['session_id']:<12} {n_csv:>4} {is_err:>6} {et:>4} {agree:>8}")
print()
print("Totals across sampled sessions:")
for a, t in totals.items():
    print(f"  {a:<14} checked={t['checked']:<3} "
          f"csv_sum={t['csv_sum']:<4} log_is_err={t['log_is_err']:<4} "
          f"log_text_err={t['log_text']:<4}")
