<div align="center">
<h1>SADE: Symptom-Aware Diagnostic Escalation for LLM-Based Network Troubleshooting</h1>

[Overview](#overview) ·
[What SADE adds](#what-sade-adds) ·
[Installation](#installation) ·
[Quick Start](#quick-start) ·
[Reproducing the paper](#reproducing-the-paper) ·
[Repo layout](#repo-layout) ·
[Acknowledgements](#acknowledgements)

</div>

> **Built on top of [NIKA](https://github.com/sands-lab/nika).** SADE uses
> NIKA's unmodified orchestrator, fault-injection platform, and four-step
> evaluation pipeline. We add a phase-gated diagnostic workflow, a 15-skill
> library, two new Claude-Code-based agents, and a reproducibility data pack
> on top — see [What SADE adds](#what-sade-adds) for the full list.

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

<h2 id="what-sade-adds">What SADE adds on top of NIKA</h2>

NIKA contributes the network-incident benchmark, the Kathará-based
fault-injection environment, and the four-step evaluation pipeline. Everything
under `src/nika/` and `src/scripts/step1`–`step4` is unmodified upstream NIKA.
SADE adds:

1. **A phase-gated diagnostic workflow** (`src/agent/prompts/sade_prompt.py`)
   — five phases (blind start → branch → symptom-first diagnosis →
   broad-search escalation → submission) that separate evidence acquisition
   from hypothesis commitment.
2. **A 15-skill library** wired into Claude Code's `Skill` tool
   (`src/agent/.claude/skills/`):
   - 12 fault-family books mapping symptoms to confirmation patterns
   - 1 diagnosis manual (`diagnosis-methodology-skill`) with 12 read-only
     helper scripts (`infra_sweep`, `l2_snapshot`, `ospf_snapshot`,
     `tc_snapshot`, `service_snapshot`, `pressure_sweep`, ...)
   - 2 utility books (`baseline-behavior-skill` for symptom gating,
     `big-return-skill` for oversized output handling)
3. **A helper-script launcher** (`h.py` at the repo root) that the agent
   invokes as `python ../../h.py <script>`. See the
   [h.py subsection](#hpy--the-sade-helper-launcher) below for usage.
4. **Two new agents** plugged into the unmodified NIKA pipeline: SADE
   (`claude-code-sade`) and CC-Baseline (`claude-code`). Both use the
   `claude-agent-sdk`.
5. **A held-out train/test split** of NIKA's 640-incident pool
   (`benchmark/benchmark_train.csv`, `benchmark/benchmark_test.csv`) so skill
   design and evaluation are kept separate.
6. **Three-way matched evaluation** across SADE / CC-Baseline / ReAct + GPT-5
   on the matched (problem, scenario, topology) triples, regenerable
   end-to-end via `Research_results/build_research_results.py`.
7. **Pipeline robustness fixes** that make 500-case batch runs feasible —
   auto Docker/Kathará recovery in `benchmark/run_benchmark.py`, native
   Claude Code SDK token accounting in `src/nika/evaluator/trace_parser.py`,
   UTF-8 explicit encoding for Windows compatibility, and skip-row recording
   for setup failures.

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
git clone https://github.com/Overlxrd-uwu/SADE-NetworkAgent.git
cd SADE-NetworkAgent
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
BASE_DIR=/absolute/path/to/SADE-NetworkAgent

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

After setup, confirm the SADE skill library and helper launcher landed.
Expected: **15** skill directories (12 fault-family + `diagnosis-methodology-skill`
+ `baseline-behavior-skill` + `big-return-skill`).

```bash
# Linux / macOS
ls src/agent/.claude/skills/ | wc -l
```

```powershell
# Windows PowerShell
(Get-ChildItem src/agent/.claude/skills/).Count
```

Then verify the helper launcher resolves the skill paths:

```bash
python h.py     # should print a usage message + helper list, not "helper not found"
```

If the count is below 15, your clone or extraction skipped hidden
directories — re-clone with `git clone` (not "Download ZIP" from the GitHub
UI), since the archive endpoint occasionally drops dot-prefixed paths.

<h2 id="quick-start">Quick Start</h2>

NIKA evaluation is a four-step pipeline. Run it once on a single incident
to confirm the install works end to end.

### Step 1 — Spin up the Kathará lab for one scenario

```bash
python src/scripts/step1_net_env_start.py --scenario simple_ospf --topo_size s
```

### Step 2 — Inject a fault

```bash
python src/scripts/step2_failure_inject.py --root_cause_name ospf_neighbor_missing
```

### Step 3 — Run the agent (pick one)

```bash
# SADE (Claude Code + phase-gated workflow + skill library)
python src/scripts/step3_agent_run.py --agent-type claude-code-sade --model claude-sonnet-4-6 --max-steps 20

# CC-Baseline (Claude Code, no SADE policy)
python src/scripts/step3_agent_run.py --agent-type claude-code      --model claude-sonnet-4-6 --max-steps 20

# ReAct + GPT-5 (original NIKA baseline)
python src/scripts/step3_agent_run.py --agent-type react            --llm-backend openai --model gpt-5 --max-steps 20
```

### Step 4 — Score the run (LLM-as-judge + grading)

```bash
python src/scripts/step4_result_eval.py --judge-model gpt-5-mini
```

A successful run appends one row to `results/0_summary/evaluation_summary.csv`
with populated `in_tokens`, `out_tokens`, `tool_calls`, judge scores, and
detection / localisation / RCA metrics.

### h.py — the SADE helper launcher

`h.py` (at the repo root) is the single entry point the SADE agent uses to
run the diagnosis-methodology helper scripts. From the agent's working
directory (`src/agent/`), it invokes them as:

```bash
python ../../h.py infra_sweep              # one-pass nft / addressing / routing / ARP / resolver / link sweep
python ../../h.py ospf_snapshot            # FRR + OSPF adjacency + per-interface state
python ../../h.py service_snapshot         # combined DNS + HTTP + localhost-HTTP + service-process
python ../../h.py                          # bare invocation lists every available helper
```

What the launcher does:

- Resolves the helper's full path under
  `src/agent/.claude/skills/diagnosis-methodology-skill/scripts/` (or
  `bgp-fault-skill/scripts/`, `big-return-skill/scripts/`).
- Forwards the rest of the argv to the helper unchanged, so
  `python ../../h.py infra_sweep --device router1` works exactly like
  invoking `infra_sweep.py --device router1` directly.
- Injects `LAB_NAME` from `runtime/current_session.json` into the helper's
  environment, so every helper targets the right Kathará lab without the
  agent having to remember it.

You can use `h.py` directly during debugging — `python h.py <script>` from
the repo root works the same way (just without the `../../` prefix the
agent uses from `src/agent/`).

### Run the full benchmark

```bash
# Iterate the four steps over benchmark/benchmark_selected.csv
python benchmark/run_benchmark.py --agent-type claude-code-sade --model claude-sonnet-4-6 --max-steps 20
```

Each row in `benchmark_selected.csv` defines one (root cause, scenario,
topology) triple. The runner tears down the Kathará lab between cases, so a
full pass on the held-out test split takes time and credits.

<h2 id="reproducing-the-paper">Reproducing the paper</h2>

`Research_results/` ships pre-computed CSVs for the test-set 3-way comparison
(SADE, CC-Baseline, ReAct + GPT-5) on the matched triples. To regenerate
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
SADE-NetworkAgent/
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

<h2 id="acknowledgements">Acknowledgements</h2>

This repository is built on top of [NIKA](https://github.com/sands-lab/nika)
— the network-troubleshooting benchmark and orchestration platform from the
SANDS Lab. NIKA contributes the 640-incident benchmark suite, the
Kathará-based fault-injection environment, the four-step evaluation pipeline,
and the LLM-as-judge scoring framework that this work depends on. SADE uses
all of those unmodified; only the agent layer and the reproducibility data
pack are ours.

Please cite the underlying NIKA benchmark when reporting numbers from this
repo.
