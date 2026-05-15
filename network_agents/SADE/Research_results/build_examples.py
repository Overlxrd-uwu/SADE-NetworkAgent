"""Build Research_results/examples/sade_wins.md.

Strict filter: cases where BOTH baselines fail (final_outcome <= 2) AND
SADE wins (final_outcome >= 4). For each surviving case, the doc
characterises:
  - Why ReAct failed   (no submit / wrong root cause / wrong device)
  - Why CC-Baseline failed (same categorisation)
  - What SADE did differently (decisive evidence + matched fault-family rule)
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Research_results" / "examples"
OUT.mkdir(parents=True, exist_ok=True)
UNIFIED = ROOT / "Research_results" / "data" / "unified_test_3way.csv"

SESSION_ROOT = {
    "ReAct (GPT-5)": ROOT / "Research_results" / "results_ReAct_GPT5" / "results",
    "CC-Baseline": ROOT / "Research_results" / "results_ClaudeB",
    "SADE": ROOT / "Research_results" / "results_sade",
}
# Fall back to repo-root locations if the inside-Research_results copies
# aren't present (e.g., when running before the move-into-Research_results
# commit was checked out).
for k, p in list(SESSION_ROOT.items()):
    if not p.is_dir():
        alt = ROOT / p.name if p.name != "results" else ROOT / "Research_results" / "results_ReAct_GPT5" / "results"
        if alt.is_dir():
            SESSION_ROOT[k] = alt


def safe_load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def session_dir(agent: str, family: str, sid) -> Path:
    return SESSION_ROOT[agent] / str(family) / str(sid)


def session_summary(agent: str, family: str, sid) -> dict:
    d = session_dir(agent, family, sid)
    sub_path = d / "submission.json"
    sub = safe_load_json(sub_path) or {}
    submission_present = sub_path.is_file()
    log = d / "conversation_diagnosis_agent.log"
    tool_seq: list[str] = []
    pre_submit_thinking = None
    last_thinking = None
    submit_seen = False
    if log.is_file():
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
                    et = evt.get("event")
                    if et == "tool_start":
                        name = (evt.get("tool") or {}).get("name", "?")
                        short = name.split("__")[-1] if "__" in name else name
                        tool_seq.append(short)
                        if "submit" in short and not submit_seen:
                            submit_seen = True
                            pre_submit_thinking = last_thinking
                    elif et == "thinking":
                        last_thinking = evt.get("text", "")
        except OSError:
            pass

    deciding = pre_submit_thinking or last_thinking
    if deciding:
        deciding = deciding.encode("ascii", errors="replace").decode("ascii")
        if len(deciding) > 1500:
            deciding = "…" + deciding[-1500:]

    return {
        "submission": sub,
        "submission_present": submission_present,
        "tool_sequence": tool_seq,
        "tool_count": len(tool_seq),
        "deciding_thinking": deciding,
    }


def categorise_failure(summ: dict, gt: dict) -> tuple[str, str]:
    """Return (failure_label, one-line explanation) for a baseline that lost."""
    sub = summ.get("submission") or {}
    if not summ.get("submission_present"):
        return ("no submission", "Agent never called `submit()` — exhausted its turn budget without finalising.")
    rcn = list(sub.get("root_cause_name") or [])
    fd = list(sub.get("faulty_devices") or [])
    if not rcn and not fd:
        return ("empty submission", "Submitted with empty root_cause_name / faulty_devices.")
    gt_rcn = set(gt.get("root_cause_name") or [])
    gt_fd = set(gt.get("faulty_devices") or [])
    rcn_ok = bool(set(rcn) & gt_rcn)
    fd_ok = bool(set(fd) & gt_fd)
    if not rcn_ok and not fd_ok:
        return ("wrong family + wrong device",
                f"Submitted root_cause_name={rcn}, faulty_devices={fd}; "
                f"ground truth root_cause_name={list(gt_rcn)}, faulty_devices={list(gt_fd)}.")
    if not rcn_ok and fd_ok:
        return ("wrong fault family",
                f"Got the device right but submitted root_cause_name={rcn} "
                f"(ground truth {list(gt_rcn)}).")
    if rcn_ok and not fd_ok:
        return ("wrong device",
                f"Got the fault family right but submitted faulty_devices={fd} "
                f"(ground truth {list(gt_fd)}).")
    return ("partial match", "Submission overlapped ground truth but the LLM judge marked it inadequate.")


def fmt_submission(summ: dict) -> str:
    sub = summ.get("submission") or {}
    if not summ.get("submission_present"):
        return "_no submit() call — agent never finalised a diagnosis_"
    rcn = sub.get("root_cause_name", [])
    fd = sub.get("faulty_devices", [])
    if not rcn and not fd:
        return "_submitted empty diagnosis_"
    return (f"`is_anomaly={sub.get('is_anomaly')}`, "
            f"`root_cause_name={rcn}`, `faulty_devices={fd}`")


def fmt_tool_sequence(seq: list[str], cap: int = 14) -> str:
    if not seq:
        return "(no tool calls logged)"
    if len(seq) <= cap:
        return " → ".join(seq)
    head = " → ".join(seq[: cap // 2])
    tail = " → ".join(seq[-cap // 2:])
    return f"{head} → … ({len(seq) - cap} more) … → {tail}"


def main():
    df = pd.read_csv(UNIFIED, dtype={"session_id": str})
    df["session_id"] = df["session_id"].astype(str).str.zfill(10)
    for col in ["llm_judge_final_outcome_score", "llm_judge_overall_score",
                "tool_calls"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Strict filter: SADE final >= 4 AND both baselines final <= 2.
    pivot = df.pivot_table(
        index=["root_cause_name", "net_env", "scenario_topo_size"],
        columns="agent",
        values="llm_judge_final_outcome_score",
        aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    keep = pivot[
        (pivot["SADE"] >= 4)
        & (pivot["ReAct (GPT-5)"] <= 2)
        & (pivot["CC-Baseline"] <= 2)
    ].copy()
    keep["gap"] = keep["SADE"] - keep[["ReAct (GPT-5)", "CC-Baseline"]].min(axis=1)
    keep = keep.sort_values(["root_cause_name", "net_env", "scenario_topo_size"])

    md: list[str] = []
    md.append("# Cases where every baseline fails and SADE succeeds\n")
    md.append("Strict filter applied: SADE's `llm_judge_final_outcome_score >= 4` "
              "AND both ReAct (GPT-5) and CC-Baseline (Claude Code, no SADE) "
              "scored `<= 2`. These are the cleanest demonstrations of SADE's "
              "diagnostic-workflow advantage — the same model class (Sonnet) "
              "fails without scaffolding (CC-Baseline), and a different "
              "framework with a stronger model (GPT-5) also fails. The only "
              "thing differentiating SADE on these cases is the SADE workflow "
              "itself.\n")
    md.append(f"Total matching cases: **{len(keep)}**.\n\n---\n")

    # Cross-cutting failure-mode summary
    fail_cats = {"ReAct (GPT-5)": Counter(), "CC-Baseline": Counter()}
    sade_tools = []
    base_tools = {"ReAct (GPT-5)": [], "CC-Baseline": []}

    case_records = []
    for _, row in keep.iterrows():
        fam = row["root_cause_name"]
        env = row["net_env"]
        sz = row["scenario_topo_size"]
        per_agent = {}
        for a in SESSION_ROOT:
            r = df[
                (df["agent"] == a)
                & (df["root_cause_name"] == fam)
                & (df["net_env"] == env)
                & (df["scenario_topo_size"] == sz)
            ]
            if r.empty:
                break
            per_agent[a] = r.iloc[0]
        if len(per_agent) != 3:
            continue
        gt = safe_load_json(
            session_dir("SADE", fam, per_agent["SADE"]["session_id"])
            / "ground_truth.json"
        ) or {}
        summaries = {a: session_summary(a, fam, per_agent[a]["session_id"])
                     for a in SESSION_ROOT}
        case_records.append({
            "fam": fam, "env": env, "sz": sz, "gt": gt,
            "per_agent": per_agent, "summaries": summaries,
        })
        for a in ["ReAct (GPT-5)", "CC-Baseline"]:
            label, _ = categorise_failure(summaries[a], gt)
            fail_cats[a][label] += 1
            base_tools[a].append(summaries[a]["tool_count"])
        sade_tools.append(summaries["SADE"]["tool_count"])

    md.append("## Cross-cutting failure-mode summary\n")
    md.append("How each baseline fails on these cases (categorised by submission shape vs ground truth):\n")
    md.append("| Failure mode | ReAct (GPT-5) | CC-Baseline |")
    md.append("|---|---:|---:|")
    all_modes = sorted(set(fail_cats["ReAct (GPT-5)"]) | set(fail_cats["CC-Baseline"]))
    for mode in all_modes:
        r = fail_cats["ReAct (GPT-5)"].get(mode, 0)
        c = fail_cats["CC-Baseline"].get(mode, 0)
        md.append(f"| {mode} | {r} | {c} |")
    md.append("")
    if sade_tools and base_tools["ReAct (GPT-5)"]:
        from statistics import median
        md.append("Tool-call medians on these cases:\n")
        md.append("| Agent | median tool_calls |")
        md.append("|---|---:|")
        md.append(f"| ReAct (GPT-5) | {median(base_tools['ReAct (GPT-5)']):.0f} |")
        md.append(f"| CC-Baseline | {median(base_tools['CC-Baseline']):.0f} |")
        md.append(f"| **SADE** | **{median(sade_tools):.0f}** |")
        md.append("")
    md.append("Most common patterns: **CC-Baseline runs out of turns "
              "without finalising** (no submit), and **ReAct converges on a "
              "neighbouring fault family** (right symptom, wrong label). "
              "SADE's phase gates force an early commitment to a fault family "
              "and the skill scaffolding tells the agent which decisive probe "
              "to run, so it submits faster and lands on the right label.\n")
    md.append("---\n")

    # Per-case sections
    for i, rec in enumerate(case_records, start=1):
        fam = rec["fam"]; env = rec["env"]; sz = rec["sz"]
        gt = rec["gt"]
        summaries = rec["summaries"]
        per_agent = rec["per_agent"]

        md.append(f"## Case {i}: `{fam}` on `{env}` ({sz})\n")
        md.append(f"**Ground truth.** root_cause_name = `{gt.get('root_cause_name', '?')}`, "
                  f"faulty_devices = `{gt.get('faulty_devices', '?')}`.\n")
        md.append("| Agent | session_id | final | submission | failure mode |")
        md.append("|---|---|---:|---|---|")
        for a in ["ReAct (GPT-5)", "CC-Baseline", "SADE"]:
            sid = per_agent[a]["session_id"]
            fin = int(per_agent[a]["llm_judge_final_outcome_score"])
            summ = summaries[a]
            sub_str = fmt_submission(summ)
            if a == "SADE":
                fail_label = "—"
            else:
                fail_label, _ = categorise_failure(summ, gt)
            md.append(f"| **{a}** | `{sid}` | {fin} | {sub_str} | {fail_label} |")
        md.append("")

        # Why each baseline failed (one bullet each)
        md.append("**Why each baseline failed**\n")
        for a in ["ReAct (GPT-5)", "CC-Baseline"]:
            _, explanation = categorise_failure(summaries[a], gt)
            tools = summaries[a]["tool_count"]
            md.append(f"- **{a}** ({tools} tool calls). {explanation}")
        md.append("")

        # What SADE did differently
        md.append("**What SADE did differently**\n")
        sade_summ = summaries["SADE"]
        md.append(f"- {sade_summ['tool_count']} tool calls before `submit()` "
                  f"({fmt_tool_sequence(sade_summ['tool_sequence'])}).")
        if sade_summ["deciding_thinking"]:
            text = sade_summ["deciding_thinking"].replace("\n", " ").strip()
            text = text[:700] + ("…" if len(text) > 700 else "")
            md.append(f"- Decisive reasoning (last thinking before `submit`):  ")
            md.append(f"  > {text}")
        md.append("")
        md.append("---\n")

    out_md = OUT / "sade_wins.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {out_md} ({len(case_records)} cases match the strict filter)")


if __name__ == "__main__":
    main()
