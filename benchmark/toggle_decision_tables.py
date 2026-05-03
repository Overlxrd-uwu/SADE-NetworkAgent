"""Toggle the `## Decision Table` / `## Decision rules` section in
OSPF, link, and BGP fault skills.

Strips the header line through the line before the next `## ` header
(i.e. removes the table and any explanatory prose that lives under the
table heading until the next section). Always backs up to SKILL.md.bak
before stripping, so `restore` is lossless.

Usage:
    python benchmark/toggle_decision_tables.py status
    python benchmark/toggle_decision_tables.py strip
    python benchmark/toggle_decision_tables.py restore
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

CUR_DIR = Path(__file__).resolve().parent
BASE_DIR = CUR_DIR.parent
SKILLS_DIR = BASE_DIR / "src" / "agent" / ".claude" / "skills"

TARGET_SKILLS = [
    "ospf-fault-skill",
    "link-fault-skill",
    "bgp-fault-skill",
]

SECTION_HEADER_RE = re.compile(r"^## (?:Decision Table|Decision rules)\s*$")
NEXT_SECTION_RE = re.compile(r"^## ")


def skill_path(name: str) -> Path:
    return SKILLS_DIR / name / "SKILL.md"


def backup_path(name: str) -> Path:
    return SKILLS_DIR / name / "SKILL.md.bak"


def strip_decision_section(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    stripped = False
    while i < len(lines):
        if not stripped and SECTION_HEADER_RE.match(lines[i].rstrip("\n")):
            i += 1
            while i < len(lines) and not NEXT_SECTION_RE.match(lines[i]):
                i += 1
            stripped = True
            continue
        out.append(lines[i])
        i += 1
    if not stripped:
        raise RuntimeError("No `## Decision Table` or `## Decision rules` section found")
    return "".join(out)


def has_section(text: str) -> bool:
    return any(SECTION_HEADER_RE.match(line) for line in text.splitlines())


def cmd_strip() -> int:
    failed = False
    for name in TARGET_SKILLS:
        src = skill_path(name)
        bak = backup_path(name)
        if not src.exists():
            print(f"[ERROR] {name}: {src} does not exist")
            failed = True
            continue
        if bak.exists():
            print(f"[SKIP]  {name}: {bak.name} already exists. "
                  f"Run `restore` first or delete the .bak manually.")
            continue
        original = src.read_text(encoding="utf-8")
        try:
            stripped = strip_decision_section(original)
        except RuntimeError as exc:
            print(f"[ERROR] {name}: {exc}")
            failed = True
            continue
        shutil.copy2(src, bak)
        src.write_text(stripped, encoding="utf-8")
        bytes_removed = len(original) - len(stripped)
        print(f"[STRIP] {name}: backed up to {bak.name}, removed {bytes_removed} bytes")
    return 1 if failed else 0


def cmd_restore() -> int:
    failed = False
    for name in TARGET_SKILLS:
        src = skill_path(name)
        bak = backup_path(name)
        if not bak.exists():
            print(f"[SKIP]    {name}: no {bak.name} found")
            continue
        shutil.copy2(bak, src)
        bak.unlink()
        print(f"[RESTORE] {name}: restored from {bak.name}")
    return 1 if failed else 0


def cmd_status() -> int:
    for name in TARGET_SKILLS:
        src = skill_path(name)
        bak = backup_path(name)
        if not src.exists():
            print(f"  {name}: SKILL.md MISSING")
            continue
        text = src.read_text(encoding="utf-8")
        header = has_section(text)
        bak_exists = bak.exists()
        if header and not bak_exists:
            state = "WITH TABLE (original)"
        elif not header and bak_exists:
            state = "STRIPPED (backup present)"
        elif header and bak_exists:
            state = "INCONSISTENT (header present AND backup exists)"
        else:
            state = "STRIPPED, NO BACKUP (cannot restore)"
        print(f"  {name:<22s} {state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("strip", help="Strip decision tables (backs up to .bak)")
    sub.add_parser("restore", help="Restore decision tables from .bak")
    sub.add_parser("status", help="Show current state of each skill")
    args = parser.parse_args()

    if args.cmd == "strip":
        return cmd_strip()
    if args.cmd == "restore":
        return cmd_restore()
    if args.cmd == "status":
        return cmd_status()
    return 2


if __name__ == "__main__":
    sys.exit(main())
