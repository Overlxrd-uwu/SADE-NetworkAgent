from pathlib import Path

from dotenv import load_dotenv

# config.py lives at <repo>/src/nika/config.py
_PKG_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_DIR.parent.parent

# MCP servers are spawned as subprocesses with an unrelated cwd; load .env from repo root.
load_dotenv(_REPO_ROOT / ".env")

RUNTIME_DIR = _REPO_ROOT / "runtime"
SESSIONS_DIR = RUNTIME_DIR / "sessions"
RESULTS_DIR = _REPO_ROOT / "results"
BENCHMARK_DIR = _REPO_ROOT / "benchmark"
MCP_SERVER_DIR = _PKG_DIR / "service" / "mcp_server"


def pkg_path(*parts: str) -> Path:
    """Return a path under the nika package root."""
    return _PKG_DIR.joinpath(*parts)
