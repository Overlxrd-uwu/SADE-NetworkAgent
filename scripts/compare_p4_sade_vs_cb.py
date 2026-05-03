"""Compare P4/SDN-related performance: SADE vs pure-Claude baseline."""

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SADE_CSV = ROOT / "results_sade" / "0_summary" / "evaluation_summary.csv"
CB_CSV = ROOT / "results_cb_s" / "0_summary" / "evaluation_summary.csv"

# P4/SDN-flavored categories.
P4_FAMILIES = {
    "bmv2_switch_down",
    "flow_rule_loop",
    "flow_rule_shadowing",
    "p4_aggressive_detection_thresholds",
    "p4_compilation_error_parser_state",
    "p4_header_definition_error",
    "p4_table_entry_misconfig",
    "p4_table_entry_missing",
    "sdn_controller_crash",
    "southbound_port_block",
    "southbound_port_mismatch",
    "mpls_label_limit_exceeded",
}


def load(csv_path):
    rows = []
    with csv_path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def num(v, default=float("nan")):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


sade = load(SADE_CSV)
cb = load(CB_CSV)
print(f"SADE rows: {len(sade)}  |  CB rows: {len(cb)}")
print()

# Per-category mean scores for P4 families.
def aggregate(rows):
    by_cat = defaultdict(list)
    for r in rows:
        if r["root_cause_name"] in P4_FAMILIES:
            by_cat[r["root_cause_name"]].append(r)
    out = {}
    for cat, group in by_cat.items():
        overall = [num(r["llm_judge_overall_score"]) for r in group]
        finalo = [num(r["llm_judge_final_outcome_score"]) for r in group]
        rca = [num(r["rca_f1"]) for r in group]
        in_t = [num(r["in_tokens"]) for r in group]
        out_t = [num(r["out_tokens"]) for r in group]
        steps = [num(r["steps"]) for r in group]
        tools = [num(r["tool_calls"]) for r in group]
        out[cat] = {
            "n": len(group),
            "overall": sum(overall) / len(overall) if overall else float("nan"),
            "final_outcome": sum(finalo) / len(finalo) if finalo else float("nan"),
            "rca_f1": sum(rca) / len(rca) if rca else float("nan"),
            "mean_in": sum(in_t) / len(in_t) if in_t else float("nan"),
            "mean_out": sum(out_t) / len(out_t) if out_t else float("nan"),
            "mean_steps": sum(steps) / len(steps) if steps else float("nan"),
            "mean_tools": sum(tools) / len(tools) if tools else float("nan"),
        }
    return out


sade_p4 = aggregate(sade)
cb_p4 = aggregate(cb)

cats = sorted(set(sade_p4) | set(cb_p4))
print(f"{'category':<42} {'n_S':>4}/{'n_CB':<4}  {'over_S':>6}/{'over_CB':<6}  {'final_S':>7}/{'final_CB':<7}  {'in_kS':>6}/{'in_kCB':<6}")
print("-" * 110)
for c in cats:
    s = sade_p4.get(c, {})
    b = cb_p4.get(c, {})
    def f(v, fmt="{:.2f}"):
        return fmt.format(v) if v == v else "  -- "
    print(
        f"{c:<42} "
        f"{s.get('n', 0):>4}/{b.get('n', 0):<4}  "
        f"{f(s.get('overall', float('nan'))):>6}/{f(b.get('overall', float('nan'))):<6}  "
        f"{f(s.get('final_outcome', float('nan'))):>7}/{f(b.get('final_outcome', float('nan'))):<7}  "
        f"{f(s.get('mean_in', float('nan'))/1000, '{:.0f}k'):>6}/{f(b.get('mean_in', float('nan'))/1000, '{:.0f}k'):<6}"
    )

print()
print("Per-session-pair detail (matched by net_env + topo_size):")

# Match same triples between SADE and CB so the comparison is apples-to-apples.
def triples(rows):
    out = defaultdict(list)
    for r in rows:
        if r["root_cause_name"] in P4_FAMILIES:
            key = (r["root_cause_name"], r["net_env"], r["scenario_topo_size"])
            out[key].append(r)
    return out


s_t = triples(sade)
c_t = triples(cb)
common = sorted(set(s_t) & set(c_t))
print(f"  matched triples: {len(common)}")
gap_rows = []
for k in common:
    s_overall = num(s_t[k][0]["llm_judge_overall_score"])
    c_overall = num(c_t[k][0]["llm_judge_overall_score"])
    s_final = num(s_t[k][0]["llm_judge_final_outcome_score"])
    c_final = num(c_t[k][0]["llm_judge_final_outcome_score"])
    s_sub = s_t[k][0]
    c_sub = c_t[k][0]
    gap_rows.append(
        (k, s_overall, c_overall, s_final, c_final,
         s_t[k][0]["session_id"], c_t[k][0]["session_id"])
    )

# Largest CB-wins-over-SADE gaps
gap_rows_sorted = sorted(gap_rows, key=lambda x: (x[2] - x[1]), reverse=True)
print()
print(f"  {'category':<40} {'env':<22} {'sz':<3}  {'S_over':>6} -> {'CB_over':>7}   {'S_fin':>5} -> {'CB_fin':>6}")
for k, so, co, sf, cf, ssid, csid in gap_rows_sorted[:15]:
    cat, env, sz = k
    print(f"  {cat:<40} {env:<22} {sz:<3}  {so:>6.1f} -> {co:>7.1f}   {sf:>5.1f} -> {cf:>6.1f}    [{ssid} vs {csid}]")
