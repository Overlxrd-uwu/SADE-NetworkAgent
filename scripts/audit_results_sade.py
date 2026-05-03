#!/usr/bin/env python
"""Audit results_sade against evaluation_summary.csv registry.

Reports:
- pairs (category, session_id) listed in the CSV but missing on disk
- pairs (category, session_id) on disk but not in the CSV (orphans)

Searches peer result trees for any missing sessions so they can be back-filled.
Does not delete or copy anything by itself; emits JSON report to stdout.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_SADE = REPO_ROOT / "results_sade"
CSV_PATH = RESULTS_SADE / "0_summary" / "evaluation_summary.csv"

def _expand_search_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    parents = [
        REPO_ROOT,
        Path(r"D:/meet/repro/nika-claude"),
        Path(r"D:/SadeAgent/re_sum"),
    ]
    for parent in parents:
        if not parent.exists():
            continue
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            name = child.name.lower()
            if not (name == "results" or name.startswith("result_") or name.startswith("results_") or name == "result_ag"):
                continue
            # Skip the destination tree itself.
            try:
                if child.resolve() == (REPO_ROOT / "results_sade").resolve():
                    continue
            except OSError:
                pass
            resolved = child.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(child)
    return roots


PEER_TREES = _expand_search_roots()

# Files we expect every session directory to contain.
SESSION_MARKER_FILES = {"session_meta.json", "submission.json"}


def read_csv_pairs(csv_path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = (row.get("root_cause_name") or "").strip()
            sid = (row.get("session_id") or "").strip()
            if cat and sid:
                pairs.append((cat, sid))
    return pairs


def list_disk_pairs(root: Path) -> set[tuple[str, str]]:
    """Return (category, session_id) pairs found as subdirectories."""
    found: set[tuple[str, str]] = set()
    if not root.exists():
        return found
    for cat_dir in root.iterdir():
        if not cat_dir.is_dir():
            continue
        if cat_dir.name == "0_summary":
            continue
        for sid_dir in cat_dir.iterdir():
            if not sid_dir.is_dir():
                continue
            found.add((cat_dir.name, sid_dir.name))
    return found


def find_in_peers(category: str, sid: str) -> list[str]:
    """Return list of peer-tree paths where this (category, sid) exists."""
    hits: list[str] = []
    for peer in PEER_TREES:
        candidate = peer / category / sid
        if candidate.is_dir():
            hits.append(str(candidate))
    return hits


def main() -> int:
    if not CSV_PATH.is_file():
        print(json.dumps({"error": f"CSV not found at {CSV_PATH}"}, indent=2))
        return 1

    csv_pairs = read_csv_pairs(CSV_PATH)
    csv_set = set(csv_pairs)
    csv_dups = [p for p in csv_pairs if csv_pairs.count(p) > 1]

    disk_set = list_disk_pairs(RESULTS_SADE)

    missing = sorted(csv_set - disk_set)
    orphans = sorted(disk_set - csv_set)

    missing_with_sources = []
    for cat, sid in missing:
        sources = find_in_peers(cat, sid)
        missing_with_sources.append(
            {"category": cat, "session_id": sid, "sources": sources}
        )

    payload = {
        "csv_path": str(CSV_PATH),
        "csv_row_count": len(csv_pairs),
        "csv_unique_pairs": len(csv_set),
        "csv_duplicates": sorted(set(csv_dups)),
        "disk_pair_count": len(disk_set),
        "missing_count": len(missing),
        "orphan_count": len(orphans),
        "missing": missing_with_sources,
        "orphans": [{"category": c, "session_id": s} for c, s in orphans],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
