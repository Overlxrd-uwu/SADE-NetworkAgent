<div align="center">
<h1>SADE: Symptom-Aware Diagnostic Escalation for LLM-Based Network Troubleshooting</h1>

[Overview](#overview) ·
[Installation](#installation) ·
[Quick Start](#quick-start) ·
[Reproducing the paper](#reproducing-the-paper) ·
[Repo layout](#repo-layout) ·
[Cite](#cite)

</div>

<h2 id="overview">Overview</h2>

SADE is a methodology-grounded LLM agent for network troubleshooting on the
[NIKA benchmark](https://github.com/sands-lab/nika). It pairs a phase-gated
diagnostic workflow that separates evidence acquisition from hypothesis
commitment with a 15-skill library (12 fault-family books, a diagnosis manual
with 12 read-only helper scripts, and 2 utility books). This repo includes
SADE plus the two baselines used in the paper:

- **SADE** — Claude Code + phase-gated workflow + skill index library
- **CC-Baseline** — same Claude Code backbone, no SADE policy
- **ReAct + GPT-5** — the original NIKA baseline

All three agents plug into the unmodified NIKA orchestrator and four-step
evaluation pipeline, so the comparison is on identical (problem, scenario,
topology) triples.

<h2 id="installation">Installation</h2>

### Requirements

- [Kathará](https://www.kathara.org/) — follow the [official installation guide](https://github.com/KatharaFramework/Kathara?tab=readme-ov-file#installation).
- Python ≥ 3.12
- Docker (Kathará dependency)
- API access:
  - **Anthropic** (for SADE and CC-Baseline runners — `claude-sonnet-4-6`)
  - **OpenAI** (for ReAct runs and the LLM-as-judge — `gpt-5-mini`)

### Setup

```bash
# Clone
git clone https://github.com/Overlxrd-uwu/Clean-SADE.git
cd Clean-SADE
```

Install Python deps. `claude-agent-sdk` is pinned in `pyproject.toml` and
ships with whichever path you pick.

**Option A — uv (recommended).** Install `uv` first if you don't have it:

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then sync and activate the venv:

```bash
uv sync
source .venv/bin/activate          # macOS / Linux
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell
```

**Option B — plain pip.**

```bash
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .\.venv\Scripts\Activate.ps1     # Windows PowerShell
pip install -e .
```

Add the current user to the `docker` group so Kathará calls don't need
`sudo` (Linux only — security implications: see Docker docs):

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Build the customised Kathará Docker images that NIKA uses for fault injection:

```bash
bash src/nika/net_env/utils/DockerFiles/build_dockers.sh
```

### Environment variables

Create a `.env` at the repo root:

```bash
BASE_DIR=/absolute/path/to/Clean-SADE

# SADE / CC-Baseline runners
ANTHROPIC_API_KEY=sk-ant-...

# ReAct runner + LLM-as-judge
OPENAI_API_KEY=sk-...

# Optional observability
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
```

### Sanity check

After setup, confirm the SADE skill library and helper launcher landed:

```bash
# 15 directories expected (12 fault-family + diagnosis-methodology + baseline + big-return)
ls src/agent/.claude/skills/ | wc -l

# Should print a usage message listing helper-script names, not "helper not found"
python h.py
```

If `ls` shows fewer than 15 skill dirs, your clone or extraction skipped
hidden directories — re-clone with `git clone` (not "download zip") because
GitHub's archive endpoint occasionally drops dot-prefixed paths.

<h2 id="quick-start">Quick Start</h2>

NIKA evaluation is a four-step pipeline. Run it once on a single incident
to confirm the install works end to end:

```bash
# 1. Spin up the Kathará lab for one scenario
python src/scripts/step1_net_env_start.py --scenario simple_ospf --topo_size s

# 2. Inject a fault
python src/scripts/step2_failure_inject.py --root_cause_name ospf_neighbor_missing

# 3. Run the agent (pick one)
python src/scripts/step3_agent_run.py --agent_type claude-code-sade --model claude-sonnet-4-6 --max_steps 20
# python src/scripts/step3_agent_run.py --agent_type claude-code      --model claude-sonnet-4-6 --max_steps 20
# python src/scripts/step3_agent_run.py --agent_type react            --llm_backend openai --model gpt-5 --max_steps 20

# 4. Score the run (LLM-as-judge + grading)
python src/scripts/step4_result_eval.py --judge_model gpt-5-mini
```

A successful run appends one row to `results/0_summary/evaluation_summary.csv`
with populated `in_tokens`, `out_tokens`, `tool_calls`, judge scores, and
detection / localisation / RCA metrics.

### Run the full benchmark

```bash
# Iterate the four steps over benchmark/benchmark_selected.csv
python benchmark/run_benchmark.py --agent_type claude-code-sade --model claude-sonnet-4-6 --max_steps 20
```

Each row in `benchmark_selected.csv` defines one (root cause, scenario,
topology) triple. The runner tears down the Kathará lab between cases, so a
full pass on the held-out test split takes time and credits.

<h2 id="reproducing-the-paper">Reproducing the paper</h2>

`Research_results/` ships pre-computed CSVs for the test-set 3-way comparison
(SADE, CC-Baseline, ReAct + GPT-5) on the 523 matched triples. To regenerate
every figure used in the paper:

```bash
pip install matplotlib numpy pandas
python Research_results/build_research_results.py
```

That writes 11 PNGs into `Research_results/figures/`. Per-session conversation
logs are not committed (they total ~580 MB); to regenerate them, re-run the
full benchmark above for each agent.

<h2 id="repo-layout">Repo layout</h2>

```
Clean-SADE/
├── benchmark/                # NIKA benchmark + selected slice
│   ├── benchmark_full.csv         # 640-incident pool
│   ├── benchmark_selected.csv     # held-out test slice (paper headline)
│   ├── benchmark_train.csv        # training split (skill design corpus)
│   ├── benchmark_test.csv         # held-out test split
│   ├── generate_benchmark.py
│   └── run_benchmark.py
├── h.py                      # SADE helper launcher (python h.py infra_sweep, etc.)
├── Research_results/         # paper data + figure regenerator
│   ├── data/                      # unified CSV + log-scanned tool-error CSV
│   ├── figures/                   # 11 PNGs (regenerated by build script)
│   ├── tables/                    # paper Table 1, per-family, time-efficiency, topology
│   └── build_research_results.py  # one-shot regenerator
├── run_nika_break.py         # manual fault-injection / verify-injection harness
└── src/
    ├── agent/
    │   ├── claude_code_agent.py        # CC-Baseline runner
    │   ├── claude_code_agent_sade.py   # SADE runner
    │   ├── react_agent.py              # ReAct + GPT-5 baseline
    │   ├── prompts/                    # baseline + sade system prompts
    │   └── .claude/skills/             # 15-skill library (SADE)
    ├── nika/                  # NIKA orchestrator (unmodified)
    └── scripts/               # step1–step4 pipeline (unmodified)
```

<h2 id="cite">Cite</h2>

If SADE is useful in your work, please cite:

```bibtex
@inproceedings{sade2026,
  title={SADE: Symptom-Aware Diagnostic Escalation for LLM-Based Network Troubleshooting},
  author={...},
  booktitle={IEEE Local Computer Networks (LCN)},
  year={2026}
}
```

Built on top of [NIKA](https://github.com/sands-lab/nika); please cite the
underlying benchmark when reporting numbers from this repo.
