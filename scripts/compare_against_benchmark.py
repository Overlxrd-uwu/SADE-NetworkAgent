"""Compare results_sade/0_summary/evaluation_summary.csv against benchmark_test.csv.

For each (problem, scenario, topo_size) in benchmark_test.csv, count how many
session rows appear in evaluation_summary.csv. Reports any gaps and any
unexpected rows.
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark" / "benchmark_test.csv"
EVAL = ROOT / "results_sade" / "0_summary" / "evaluation_summary.csv"
SKIPS = ROOT / "results_sade" / "0_summary" / "benchmark_skips.csv"

# benchmark_test: one row per (problem, scenario, topo_size) tuple.
bench_rows = []
with BENCH.open(encoding="utf-8") as f:
    for row in csv.DictReader(f):
        bench_rows.append((row["problem"].strip(),
                           row["scenario"].strip(),
                           row["topo_size"].strip()))

bench_set = set(bench_rows)

# evaluation_summary: rows we have results for.
eval_triples = []
with EVAL.open(encoding="utf-8") as f:
    for row in csv.DictReader(f):
        eval_triples.append((row["root_cause_name"].strip(),
                             row["net_env"].strip(),
                             row["scenario_topo_size"].strip()))

eval_count = Counter(eval_triples)
eval_set = set(eval_triples)

# Skip records (deployment failures — not expected to be in eval CSV).
skip_set = set()
if SKIPS.exists():
    with SKIPS.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            skip_set.add((row["problem"].strip(),
                          row["scenario"].strip(),
                          row["topo_size"].strip()))

# Each benchmark row should have at least one eval row (more is fine if reruns).
missing = sorted(bench_set - eval_set - skip_set)
in_skips_only = sorted((bench_set - eval_set) & skip_set)
unexpected = sorted(eval_set - bench_set)
duplicates = sorted([t for t, n in eval_count.items() if n > 1])

print("BENCHMARK COVERAGE REPORT")
print("=" * 60)
print(f"benchmark_test.csv      : {len(bench_rows)} rows ({len(bench_set)} unique)")
print(f"evaluation_summary.csv  : {len(eval_triples)} rows ({len(eval_set)} unique triples)")
print(f"benchmark_skips.csv     : {len(skip_set)} skip records")
print()
print(f"Missing from results    : {len(missing)} (in benchmark_test, no eval row, not skipped)")
print(f"Skip-only coverage      : {len(in_skips_only)} (in benchmark_test, only in skips)")
print(f"Unexpected in eval      : {len(unexpected)} (in eval_summary but not in benchmark_test)")
print(f"Duplicate eval triples  : {len(duplicates)} triples have >1 eval row each")

if missing:
    print()
    print("--- MISSING (need to run) ---")
    by_problem = defaultdict(list)
    for t in missing:
        by_problem[t[0]].append(t)
    for problem in sorted(by_problem):
        items = by_problem[problem]
        print(f"  {problem}  ({len(items)})")
        for p, s, ts in items:
            print(f"    {s} / topo_size={ts}")

if in_skips_only:
    print()
    print(f"--- COVERED ONLY BY SKIPS ({len(in_skips_only)}) ---")
    for t in in_skips_only[:20]:
        print(" ", t)
    if len(in_skips_only) > 20:
        print(f"  ... +{len(in_skips_only)-20} more")

if unexpected:
    print()
    print(f"--- UNEXPECTED IN EVAL_SUMMARY ({len(unexpected)}) ---")
    for t in unexpected[:20]:
        print(" ", t, f"x{eval_count[t]}")
    if len(unexpected) > 20:
        print(f"  ... +{len(unexpected)-20} more")

if duplicates:
    print()
    print(f"--- DUPLICATES IN EVAL ({len(duplicates)} triples) ---")
    for t in duplicates[:20]:
        print(" ", t, f"-> {eval_count[t]} rows")
    if len(duplicates) > 20:
        print(f"  ... +{len(duplicates)-20} more")
