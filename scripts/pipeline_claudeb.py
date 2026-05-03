"""All-in-one pipeline for results_ClaudeB:
1. Audit registry consistency (CSV <-> directories)
2. Detect duplicates / redundancy in CSV
3. Sync (copy missing from peer trees, remove orphans)
4. Augment in_tokens / out_tokens from session logs

Run with `--dry-run` to preview without filesystem changes.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_TREE = REPO_ROOT / "results_ClaudeB"
CSV_PATH = TARGET_TREE / "0_summary" / "evaluation_summary.csv"

# Source priority: results_cb_s first (the user identified it as the reference),
# then any other result_* tree on disk. Skip TARGET_TREE itself.
PEER_PRIORITY = [
    REPO_ROOT / "results_cb_s",
]

PEER_DISCOVERY_PARENTS = [
    REPO_ROOT,
    Path(r"D:/meet/repro/nika-claude"),
    Path(r"D:/SadeAgent/re_sum"),
]


def discover_peer_trees() -> list[Path]:
    seen = set()
    roots: list[Path] = []
    for p in PEER_PRIORITY:
        if p.is_dir() and p.resolve() != TARGET_TREE.resolve():
            roots.append(p)
            seen.add(p.resolve())

    for parent in PEER_DISCOVERY_PARENTS:
        if not parent.exists():
            continue
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            name = child.name.lower()
            if not (name == "results" or name.startswith("result_") or name.startswith("results_")):
                continue
            try:
                resolved = child.resolve()
            except OSError:
                continue
            if resolved == TARGET_TREE.resolve():
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(child)
    return roots


PEER_TREES = discover_peer_trees()


def read_csv():
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return fieldnames, rows


def list_disk_pairs() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    if not TARGET_TREE.exists():
        return found
    for cat_dir in TARGET_TREE.iterdir():
        if not cat_dir.is_dir() or cat_dir.name == "0_summary":
            continue
        for sid_dir in cat_dir.iterdir():
            if not sid_dir.is_dir():
                continue
            found.add((cat_dir.name, sid_dir.name))
    return found


def find_in_peers(category: str, sid: str) -> list[str]:
    hits: list[str] = []
    for peer in PEER_TREES:
        candidate = peer / category / sid
        if candidate.is_dir():
            hits.append(str(candidate))
    return hits


def detect_duplicates(rows: list[dict]) -> dict:
    """Find duplicates by:
    - exact (category, session_id)
    - exact (category, net_env, scenario_topo_size) triple — same scenario run twice
    """
    pair_counter = Counter((r["root_cause_name"].strip(), r["session_id"].strip()) for r in rows)
    triple_counter = Counter(
        (r["root_cause_name"].strip(), r["net_env"].strip(), r["scenario_topo_size"].strip())
        for r in rows
    )
    pair_dups = {k: v for k, v in pair_counter.items() if v > 1}
    triple_dups = {k: v for k, v in triple_counter.items() if v > 1}
    return {
        "pair_duplicates": pair_dups,
        "triple_duplicates": triple_dups,
    }


def parse_last_llm_end(log: Path) -> Optional[dict]:
    if not log.is_file():
        return None
    try:
        with log.open(encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
    except OSError:
        return None
    for raw in reversed(lines[-10:]):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if obj.get("event") == "llm_end":
            return obj
    return None


def coerce_int(value) -> int:
    if value in (None, "", "0", "0.0"):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Full pipeline for results_ClaudeB.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"=== Pipeline: results_ClaudeB ===")
    print(f"target  : {TARGET_TREE}")
    print(f"csv     : {CSV_PATH}")
    print(f"peers   : {[str(p) for p in PEER_TREES[:5]]} ...({len(PEER_TREES)} total)")
    print()

    fieldnames, rows = read_csv()
    csv_pairs = [(r["root_cause_name"].strip(), r["session_id"].strip()) for r in rows]
    csv_set = set(csv_pairs)
    disk_set = list_disk_pairs()

    # --- Step 1: detect duplicates ---
    dups = detect_duplicates(rows)
    print(f"=== Step 1: duplicate detection ===")
    print(f"  csv rows total   : {len(rows)}")
    print(f"  unique (cat,sid) : {len(csv_set)}")
    print(f"  pair duplicates  : {len(dups['pair_duplicates'])}")
    print(f"  triple dups (same cat+env+topo run multiple times): {len(dups['triple_duplicates'])}")
    if dups["pair_duplicates"]:
        print("  --- exact (cat, session_id) duplicates ---")
        for (cat, sid), n in sorted(dups["pair_duplicates"].items()):
            print(f"    {cat}/{sid} x{n}")
    if dups["triple_duplicates"]:
        print(f"  --- (cat, net_env, topo_size) duplicates (top 20) ---")
        for triple, n in sorted(dups["triple_duplicates"].items(), key=lambda x: -x[1])[:20]:
            print(f"    {triple} x{n}")
    print()

    # --- Step 2: registry audit (missing/orphans) ---
    missing = sorted(csv_set - disk_set)
    orphans = sorted(disk_set - csv_set)
    missing_with_sources = []
    for cat, sid in missing:
        sources = find_in_peers(cat, sid)
        missing_with_sources.append({"category": cat, "session_id": sid, "sources": sources})

    print(f"=== Step 2: registry audit ===")
    print(f"  disk pairs       : {len(disk_set)}")
    print(f"  missing (csv-disk): {len(missing)}")
    print(f"  orphans (disk-csv): {len(orphans)}")
    no_src = [m for m in missing_with_sources if not m["sources"]]
    if missing_with_sources:
        print(f"  missing breakdown — with-source: {len(missing_with_sources)-len(no_src)} | no-source: {len(no_src)}")
    if no_src:
        print(f"  --- {len(no_src)} missing with NO peer source ---")
        for m in no_src[:20]:
            print(f"    {m['category']}/{m['session_id']}")
    print()

    # --- Step 3: sync (copy missing, remove orphans) ---
    print(f"=== Step 3: sync ===")
    if args.dry_run:
        print("  (dry-run — not executing)")
        for m in missing_with_sources:
            if m["sources"]:
                print(f"  COPY  {m['sources'][0]} -> {TARGET_TREE / m['category'] / m['session_id']}")
        for cat, sid in orphans:
            print(f"  RMRF  {TARGET_TREE / cat / sid}")
    else:
        copies_ok = copies_err = 0
        for m in missing_with_sources:
            if not m["sources"]:
                continue
            src = Path(m["sources"][0])
            dst = TARGET_TREE / m["category"] / m["session_id"]
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                copies_ok += 1
            except Exception as exc:
                copies_err += 1
                print(f"  COPY ERR {m['category']}/{m['session_id']}: {exc}")
        removals_ok = removals_err = 0
        for cat, sid in orphans:
            path = TARGET_TREE / cat / sid
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    removals_ok += 1
            except Exception as exc:
                removals_err += 1
                print(f"  RMRF ERR {cat}/{sid}: {exc}")
        print(f"  copies  ok={copies_ok}  err={copies_err}  no-source-skipped={len(no_src)}")
        print(f"  removes ok={removals_ok}  err={removals_err}")
    print()

    # --- Step 4: token augmentation ---
    print(f"=== Step 4: token augmentation ===")
    if args.dry_run:
        print("  (dry-run — not executing)")
        return 0

    # Re-read rows after sync to reflect any new directories.
    fieldnames, rows = read_csv()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = CSV_PATH.with_suffix(f".csv.bak.{timestamp}")
    shutil.copy2(CSV_PATH, backup)

    if "in_tokens" not in fieldnames or "out_tokens" not in fieldnames:
        print("  ERROR: expected in_tokens / out_tokens columns")
        return 1

    updated = 0
    no_log: list[dict] = []
    no_llm_end: list[dict] = []
    no_tokens: list[dict] = []

    for row in rows:
        cat = row["root_cause_name"].strip()
        sid = row["session_id"].strip()
        log = TARGET_TREE / cat / sid / "conversation_diagnosis_agent.log"
        if not log.is_file():
            no_log.append({"category": cat, "session_id": sid})
            continue
        evt = parse_last_llm_end(log)
        if evt is None:
            no_llm_end.append({"category": cat, "session_id": sid})
            continue
        # Two log shapes: SADE logger emits a post-processed `tokens` block
        # with `total_input_tokens`; the plain claude-code logger only emits
        # the raw SDK `usage`. Fall back to `usage` when `tokens` is absent.
        tokens = evt.get("tokens") or {}
        usage = evt.get("usage") or {}
        source = tokens if tokens else usage
        total_in = tokens.get("total_input_tokens")
        if total_in is None:
            total_in = (
                coerce_int(source.get("input_tokens"))
                + coerce_int(source.get("cache_creation_input_tokens"))
                + coerce_int(source.get("cache_read_input_tokens"))
            )
        else:
            total_in = coerce_int(total_in)
        out_tok = coerce_int(source.get("output_tokens"))
        if total_in == 0 and out_tok == 0:
            no_tokens.append({"category": cat, "session_id": sid})
            continue
        row["in_tokens"] = str(total_in)
        row["out_tokens"] = str(out_tok)
        updated += 1

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  backup           : {backup}")
    print(f"  rows updated     : {updated}/{len(rows)}")
    print(f"  no log           : {len(no_log)}")
    print(f"  no llm_end       : {len(no_llm_end)}")
    print(f"  no tokens block  : {len(no_tokens)}")
    if no_log:
        for x in no_log[:10]:
            print(f"    no-log: {x['category']}/{x['session_id']}")
        if len(no_log) > 10:
            print(f"    ... +{len(no_log)-10} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
