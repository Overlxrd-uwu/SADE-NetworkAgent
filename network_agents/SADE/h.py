#!/usr/bin/env python
"""
Tiny launcher for diagnosis-methodology helper scripts.

Usage from any cwd:
    python h.py <script_name> [args...]

`script_name` may include or omit the `.py` suffix. The launcher locates the
script under `src/agent/.claude/skills/diagnosis-methodology-skill/scripts/`
and runs it with the project's `.venv` interpreter so the helper picks up
its dependencies. This exists so the agent does not have to remember (or
typo) the long path to each helper.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
# Locate the project venv. When SADE runs standalone, the venv lives next to
# this file (./.venv/). When SADE is embedded as a contributor agent under
# <nika-repo>/network_agents/SADE/, the venv lives at the outer repo root
# (../../.venv/). Check local first, then embedded, then fall back to the
# interpreter that invoked this launcher.
_VENV_REL = (
    os.path.join(".venv", "Scripts", "python.exe")
    if sys.platform == "win32"
    else os.path.join(".venv", "bin", "python")
)
_VENV_LOCAL = os.path.join(ROOT, _VENV_REL)
_VENV_EMBED = os.path.join(ROOT, "..", "..", _VENV_REL)
if os.path.exists(_VENV_LOCAL):
    PYTHON = _VENV_LOCAL
elif os.path.exists(_VENV_EMBED):
    PYTHON = _VENV_EMBED
else:
    PYTHON = sys.executable
SCRIPTS = os.path.join(
    ROOT, "src", "agent", ".claude", "skills",
    "diagnosis-methodology-skill", "scripts",
)
# Same standalone-vs-embedded layout reasoning as PYTHON above: the runtime
# session file lives at the project root, which is either this dir (standalone
# SADE) or two levels up (SADE embedded in a parent repo's contributor pool).
_SESSION_LOCAL = os.path.join(ROOT, "runtime", "current_session.json")
_SESSION_EMBED = os.path.join(ROOT, "..", "..", "runtime", "current_session.json")
SESSION_FILE = _SESSION_LOCAL if os.path.exists(_SESSION_LOCAL) else _SESSION_EMBED
# Special-purpose scripts not in the diagnosis-methodology folder.
EXTRA_SCRIPTS = {
    "parse_large": os.path.join(
        ROOT, "src", "agent", ".claude", "skills",
        "big-return-skill", "scripts", "parse_large_output.py",
    ),
    "bgp_snapshot": os.path.join(
        ROOT, "src", "agent", ".claude", "skills",
        "bgp-fault-skill", "scripts", "bgp_snapshot.py",
    ),
}


def _child_env() -> dict:
    """Inherit parent env, but inject LAB_NAME from the running session if unset.

    Helper scripts default to a hardcoded lab when LAB_NAME is missing. The
    Bash tool spawns h.py outside the MCP launch context, so LAB_NAME does
    not flow through. Read it from runtime/current_session.json instead so
    every lab — not just ospf_enterprise_dhcp — works.
    """
    env = os.environ.copy()
    if env.get("LAB_NAME"):
        return env
    try:
        with open(SESSION_FILE, "r") as f:
            meta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return env
    scenario = meta.get("scenario_name")
    if scenario:
        env["LAB_NAME"] = scenario
    return env


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write(
            "usage: python h.py <script_name> [args...]\n"
            f"available scripts under {SCRIPTS}:\n"
        )
        for name in sorted(os.listdir(SCRIPTS)):
            if name.endswith(".py") and not name.startswith("_"):
                sys.stderr.write(f"  {name[:-3]}\n")
        sys.stderr.write("special:\n")
        for name in EXTRA_SCRIPTS:
            sys.stderr.write(f"  {name}\n")
        return 2

    env = _child_env()

    name = sys.argv[1]
    if name in EXTRA_SCRIPTS:
        return subprocess.call([PYTHON, EXTRA_SCRIPTS[name]] + sys.argv[2:], env=env)

    if not name.endswith(".py"):
        name += ".py"
    script_path = os.path.join(SCRIPTS, name)
    if not os.path.isfile(script_path):
        sys.stderr.write(f"helper not found: {script_path}\n")
        return 2

    return subprocess.call([PYTHON, script_path] + sys.argv[2:], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
