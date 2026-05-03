"""Print a one-shot summary of scripts/audit_report.json."""
import json
from collections import Counter
from pathlib import Path

with open(Path(__file__).resolve().parent / "audit_report.json", encoding="utf-8") as f:
    p = json.load(f)

print("PRE-SYNC AUDIT:")
print("  csv_rows  :", p["csv_row_count"])
print("  csv_unique:", p["csv_unique_pairs"])
print("  csv_dups  :", len(p["csv_duplicates"]))
print("  disk      :", p["disk_pair_count"])
print("  missing   :", p["missing_count"])
print("  orphans   :", p["orphan_count"])

no_src = [m for m in p["missing"] if not m["sources"]]
multi = [m for m in p["missing"] if len(m["sources"]) > 1]
single = [m for m in p["missing"] if len(m["sources"]) == 1]
print("  missing breakdown -- no_src:", len(no_src),
      "| single:", len(single), "| multi:", len(multi))

src_counter = Counter()
for m in p["missing"]:
    if m["sources"]:
        s = m["sources"][0].replace("\\", "/")
        for prefix in ("D:/SadeAgent/SADE-Agent/", "D:/meet/repro/nika-claude/"):
            if s.startswith(prefix):
                tree = s[len(prefix):].split("/")[0]
                src_counter[tree] += 1
                break

print()
print("Source trees for missing-with-source:")
for s, n in src_counter.most_common():
    print(f"  {s}: {n}")

if no_src:
    print()
    print(f"--- {len(no_src)} no-source missing entries ---")
    for m in no_src:
        print(" ", m["category"], m["session_id"])

if multi:
    print()
    print(f"--- {len(multi)} multi-source entries (will pick local SADE-Agent) ---")
    for m in multi[:10]:
        print(" ", m["category"], m["session_id"])
        for s in m["sources"]:
            print("    <-", s)

# Orphan summary
orphan_by_cat = Counter(o["category"] for o in p["orphans"])
if orphan_by_cat:
    print()
    print(f"--- {p['orphan_count']} orphans by category ---")
    for c, n in sorted(orphan_by_cat.items()):
        print(f"  {c}: {n}")
