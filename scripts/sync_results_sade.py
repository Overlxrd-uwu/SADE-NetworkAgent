#!/usr/bin/env python
"""Sync results_sade against the registry produced by audit_results_sade.py.

Reads scripts/audit_report.json and:
- copies each missing session from its first available peer source
  (preferring SADE-Agent local trees when multiple sources exist)
- removes each orphan session directory
- writes scripts/sync_manifest.json describing every action taken

Pass `--dry-run` to print the planned actions without touching the filesystem.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_REPORT = REPO_ROOT / "scripts" / "audit_report.json"
RESULTS_SADE = REPO_ROOT / "results_sade"
MANIFEST_PATH = REPO_ROOT / "scripts" / "sync_manifest.json"

LOCAL_PREFIX = str(REPO_ROOT).replace("\\", "/").lower()


def _pick_source(sources: list[str]) -> str:
    """Prefer a source under the SADE-Agent repo when multiple exist."""
    if not sources:
        return ""
    for src in sources:
        if src.replace("\\", "/").lower().startswith(LOCAL_PREFIX):
            return src
    return sources[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync results_sade against registry.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing.")
    args = parser.parse_args()

    with AUDIT_REPORT.open(encoding="utf-8") as f:
        audit = json.load(f)

    copies: list[dict] = []
    removals: list[dict] = []
    skipped_no_source: list[dict] = []

    for missing in audit["missing"]:
        cat = missing["category"]
        sid = missing["session_id"]
        sources = missing["sources"]
        if not sources:
            skipped_no_source.append({"category": cat, "session_id": sid})
            continue
        src = _pick_source(sources)
        dst = RESULTS_SADE / cat / sid
        copies.append({"category": cat, "session_id": sid, "source": src, "dest": str(dst)})

    for orphan in audit["orphans"]:
        cat = orphan["category"]
        sid = orphan["session_id"]
        path = RESULTS_SADE / cat / sid
        removals.append({"category": cat, "session_id": sid, "path": str(path)})

    print(f"Plan: copy {len(copies)} session(s), remove {len(removals)} orphan(s), "
          f"skip {len(skipped_no_source)} without source.")

    if args.dry_run:
        print("Dry run — no filesystem changes.")
        manifest = {
            "dry_run": True,
            "copies": copies,
            "removals": removals,
            "skipped_no_source": skipped_no_source,
        }
        with MANIFEST_PATH.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return 0

    copy_results: list[dict] = []
    for entry in copies:
        src = Path(entry["source"])
        dst = Path(entry["dest"])
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            copy_results.append({**entry, "status": "ok"})
        except Exception as exc:
            copy_results.append({**entry, "status": "error", "error": str(exc)})

    remove_results: list[dict] = []
    for entry in removals:
        path = Path(entry["path"])
        try:
            if path.is_dir():
                shutil.rmtree(path)
                remove_results.append({**entry, "status": "ok"})
            else:
                remove_results.append({**entry, "status": "missing"})
        except Exception as exc:
            remove_results.append({**entry, "status": "error", "error": str(exc)})

    manifest = {
        "dry_run": False,
        "copies": copy_results,
        "removals": remove_results,
        "skipped_no_source": skipped_no_source,
        "summary": {
            "copies_ok": sum(1 for c in copy_results if c["status"] == "ok"),
            "copies_error": sum(1 for c in copy_results if c["status"] == "error"),
            "removals_ok": sum(1 for r in remove_results if r["status"] == "ok"),
            "removals_missing": sum(1 for r in remove_results if r["status"] == "missing"),
            "removals_error": sum(1 for r in remove_results if r["status"] == "error"),
            "skipped_no_source": len(skipped_no_source),
        },
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("Manifest written to", MANIFEST_PATH)
    print(json.dumps(manifest["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
