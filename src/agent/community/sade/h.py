#!/usr/bin/env python
"""Tiny launcher for diagnosis-methodology helper scripts.

Usage from the agent's working directory (this package directory):
    python h.py <script_name> [args...]

`script_name` may include or omit the `.py` suffix. The launcher locates the
script under `.claude/skills/diagnosis-methodology-skill/scripts/` (next to
this file) and runs it with the project's `.venv` interpreter so the helper
picks up its dependencies. This exists so the agent does not have to remember
(or typo) the long path to each helper.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# This file lives at <repo>/src/agent/community/sade/h.py; the skill library is
# a sibling `.claude/` directory and the project `.venv` is at the repo root.
ROOT = Path(__file__).resolve().parent

_VENV_REL = (
    Path(".venv") / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else Path(".venv") / "bin" / "python"
)


def _find_python() -> str:
    """Interpreter with the `nika` package installed.

    Walk up from this file until a project `.venv` is found (works for both the
    standalone SADE layout and the embedded `src/agent/community/sade` layout),
    then fall back to the interpreter that launched this script.
    """
    for base in (ROOT, *ROOT.parents):
        candidate = base / _VENV_REL
        if candidate.exists():
            return str(candidate)
    return sys.executable


PYTHON = _find_python()

SKILLS_DIR = ROOT / ".claude" / "skills"
SCRIPTS = SKILLS_DIR / "diagnosis-methodology-skill" / "scripts"

# Special-purpose scripts that live outside the diagnosis-methodology folder.
EXTRA_SCRIPTS = {
    "parse_large": SKILLS_DIR / "big-return-skill" / "scripts" / "parse_large_output.py",
    "bgp_snapshot": SKILLS_DIR / "bgp-fault-skill" / "scripts" / "bgp_snapshot.py",
}


def _repo_root() -> Path:
    """Outer NIKA repo root (src/agent/community/sade -> four levels up)."""
    return ROOT.parents[3] if len(ROOT.parents) >= 4 else ROOT


def _lab_name_from_session() -> str | None:
    """Resolve the running lab name from the active NIKA session, if any.

    The Bash tool spawns h.py outside the MCP launch context, so LAB_NAME does
    not flow through. The agent exports NIKA_SESSION_ID; read the scenario from
    that session's ``run.json`` under ``results/<id>/``. Falls back to the
    legacy standalone ``runtime/current_session.json``.
    """
    candidates: list[Path] = []
    session_id = os.environ.get("NIKA_SESSION_ID")
    if session_id:
        candidates.append(_repo_root() / "results" / session_id / "run.json")
    candidates.append(_repo_root() / "runtime" / "current_session.json")
    candidates.append(ROOT / "runtime" / "current_session.json")
    for path in candidates:
        try:
            meta = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        for key in ("scenario_name", "scenario", "lab_name"):
            if meta.get(key):
                return str(meta[key])
    return None


def _child_env() -> dict:
    """Inherit parent env, injecting LAB_NAME from the running session if unset."""
    env = os.environ.copy()
    if env.get("LAB_NAME"):
        return env
    lab = _lab_name_from_session()
    if lab:
        env["LAB_NAME"] = lab
    return env


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(
            "usage: python h.py <script_name> [args...]\n"
            f"available scripts under {SCRIPTS}:\n"
        )
        if SCRIPTS.is_dir():
            for name in sorted(p.name for p in SCRIPTS.glob("*.py")):
                if not name.startswith("_"):
                    sys.stderr.write(f"  {name[:-3]}\n")
        sys.stderr.write("special:\n")
        for name in EXTRA_SCRIPTS:
            sys.stderr.write(f"  {name}\n")
        return 2

    env = _child_env()
    name = sys.argv[1]

    if name in EXTRA_SCRIPTS:
        return subprocess.call([PYTHON, str(EXTRA_SCRIPTS[name])] + sys.argv[2:], env=env)

    if not name.endswith(".py"):
        name += ".py"
    script_path = SCRIPTS / name
    if not script_path.is_file():
        sys.stderr.write(f"helper not found: {script_path}\n")
        return 2

    return subprocess.call([PYTHON, str(script_path)] + sys.argv[2:], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
