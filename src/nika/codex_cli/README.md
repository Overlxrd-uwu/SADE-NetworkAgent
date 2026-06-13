# Codex CLI reference

Python package: `nika.codex_cli` (directory `src/nika/codex_cli/`). A separate Claude CLI front-end may be added alongside this module later.

Entry point: `nika` (see `[project.scripts]` in `pyproject.toml`). During development use `uv run nika …`.

Runtime paths (`runtime/`, `results/`, `benchmark/`) resolve from the repository root (derived from the installed `nika` package location). A `.env` file at the repo root is loaded automatically.

## Command tree

| Group | Purpose |
|--------|---------|
| `nika session` | List, inspect, and close active troubleshooting sessions |
| `nika env` | List / deploy Kathará scenarios and create a session |
| `nika failure` | List, describe, inject, and inspect faults for a running session |
| `nika exec` | Run a shell command inside a lab host container |
| `nika agent` | Run a troubleshooting agent on one selected session task |
| `nika eval` | Metrics, LLM judge, publish, and offline summary CSV for closed sessions |
| `nika benchmark` | Full pipeline for benchmark CSV rows or a single `(scenario, problem)` case |
| `nika traffic` | Synthetic traffic (`od`, `web`) against the running lab |

Use `nika <group> --help` and `nika <group> <command> --help` for generated option text.

## Global conventions

### Sessions and `--session-id`

- **`nika env run`** prints `session_id=…` and writes `runtime/sessions/{session_id}.json`.
- Most commands that operate on a lab accept **`--session-id`** to target a specific session.
- When **`--session-id` is omitted** and exactly **one** session is running, that session is selected automatically. With zero or multiple running sessions, the CLI raises an error asking you to pass `--session-id` or reduce concurrency.
- **`nika session close`** undeploys the Kathará lab and clears runtime session state (confirmation prompt skippable with `-y` / `--yes`).

### Topology tier (`-t` / `--tier`)

Same semantics as `nika env run`:

- **Scalable** scenarios (see `TOPO_SIZE` on lab classes under `src/nika/net_env`) require **`-t s`**, **`-t m`**, or **`-t l`**.
- **Non-scalable** scenarios must **omit** `-t`.

This flag is reused on **`nika benchmark run`** and **`nika traffic run`** when a tier is required and not already implied by the session.

### Agent options

Aligned with `nika agent run`:

- **`-a` / `--agent`**: `react` (LangGraph + LangChain ReAct), `cli` (LangGraph + Codex CLI subprocess), or `mock` (pipeline testing without an LLM).
- **`-b` / `--backend`**: LLM provider for `react` and `mock` (`openai`, `ollama`, `deepseek`). Ignored for `cli` (Codex uses OpenAI models).
- **`-m` / `--model`**: model id.
- **`-n` / `--max-steps`**: max ReAct recursion steps per phase (`react` and `mock` only).
- **`-e` / `--reasoning-effort`**: Codex `model_reasoning_effort` (`cli` only): `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.

`nika eval judge` uses **`-b`** and **`-m`** for the judge only (no agent in that command).

### Benchmark judge options

`nika benchmark run` configures **both** agent and judge in one command. By default it runs **metrics and publish only**; pass **`--judge`** to also run the LLM judge. Judge options use a **prefix** to avoid clashing with the agent:

- **`--judge`**: enable LLM-as-judge after metrics.
- **`--judge-backend`**
- **`--judge-model`**

Both judge options are required when **`--judge`** is set.

---

## `nika session`

- **`nika session ps [-a]`**: list sessions. Default: running only; **`-a` / `--all`** includes finished sessions. Columns: session id, env id, scenario name, status, failure count, agent summary.
- **`nika session inspect [SESSION_ID]`**: print the session document as JSON plus a table of `failure_injections`. Auto-selects when only one session is running.
- **`nika session close [SESSION_ID | all] [-y]`**: undeploy the lab, mark failure records ended, and remove the runtime session file. Pass **`all`** to close every running session; **`-y`** skips the confirmation prompt.

---

## `nika env`

- **`nika env list`**: print registered scenario ids.
- **`nika env run NAME [-t s|m|l] [--no-redeploy] [--instance-tag TAG]`**: deploy one instance, create a session, and print `session_id=…`.
- **`nika env ps`**: list running lab instances (one row per deployed Kathará lab). Columns: env id, topology, status, age, active session count, endpoint.

---

## `nika failure`

- **`nika failure list`**: injectable problem ids.
- **`nika failure describe PROBLEM`**: print the typed parameter schema (JSON Schema or legacy field list) and an example `nika failure inject … --set …` line.
- **`nika failure inject PROBLEM [PROBLEM …] [--session-id ID] [--set key=value …]`**: inject for a selected running session and write ground truth. Repeat **`--set`** to override injection parameters (see `describe` for valid keys).
- **`nika failure ps [--session-id ID]`**: list persisted failure injection records for one session.

---

## `nika exec`

Run a shell command inside a host container for the selected session-bound lab:

```shell
nika exec HOST COMMAND… [--session-id ID] [--timeout SECONDS]
```

- **`HOST`**: container / pc name in the lab (e.g. `pc1`).
- **`COMMAND`**: passed to the container shell (remaining args are joined with spaces).
- **`--timeout`**: default `10` seconds.

Example: `nika exec pc1 ping -c 3 10.0.0.2 --timeout 30`

---

## `nika agent`

- **`nika agent list`**: supported agent types (`react`, `cli`, `mock`), LLM backends, and Codex reasoning-effort levels.
- **`nika agent run`**: run the agent on one selected session.

  | Flag | Applies to | Meaning |
  |------|------------|---------|
  | `-a` / `--agent` | all | `react`, `cli`, or `mock` |
  | `-b` / `--backend` | `react`, `mock` | `openai`, `ollama`, or `deepseek` |
  | `-m` / `--model` | all | model id |
  | `-n` / `--max-steps` | `react`, `mock` | ReAct step cap per phase |
  | `-e` / `--reasoning-effort` | `cli` | Codex reasoning effort level |
  | `--session-id` | all | target session |

  Examples:

  ```shell
  nika agent run -a react -b openai -m gpt-5-mini -n 20
  nika agent run -a cli -m gpt-5.4-mini -e medium
  nika agent run -a mock -n 5
  ```

---

## `nika eval`

Eval commands operate on **closed** sessions only. Close the lab with **`nika session close`** before running eval; artifacts are read from and written to `results/{session_id}/`.

- **`nika eval metrics [--session-id ID]`**: rule-based metrics → `eval_metrics.json`.
- **`nika eval judge -b BACKEND -m MODEL [--session-id ID]`**: LLM judge → `llm_judge.json`.
- **`nika eval publish [--session-id ID]`**: validate eval artifacts on a closed session and record publish completion.
- **`nika eval summary [filters] [-o PATH]`**: scan finished sessions under `results/` and write one CSV.
- **`nika eval clean [-y] [--force]`**: delete historical artifacts under `results/` and runtime session JSON files. Refuses when running sessions exist unless **`--force`** is passed.

### `nika eval summary` filters

All filters are optional and repeatable. Omit filters to include every finished session that has the required artifacts.

| Option | Meaning |
|--------|---------|
| `-o` / `--output` | Output CSV path (default: `results/0_summary/evaluation_summary.csv`) |
| `-p` / `--problem` | Root-cause / problem id (e.g. `link_down`) |
| `-e` / `--env` | Scenario / net env (e.g. `simple_bgp`) |
| `-c` / `--category` | Root-cause category (e.g. `link_failure`) |
| `--session-id` | Specific session id |
| `-a` / `--agent` | Agent type |
| `--model` | Agent model id |

Each finished session directory should contain at least `run.json`, `ground_truth.json`, and `eval_metrics.json`. `llm_judge.json` is optional and merged when present.

---

## `nika benchmark`

Implements the end-to-end benchmark pipeline: start env → inject → agent → close session → eval (metrics, optional judge, publish). Run `nika eval summary` afterward to aggregate CSV rows across finished sessions.

### Batch mode (default)

Omit the `SCENARIO` positional argument. Rows are read from a CSV file.

```shell
nika benchmark run
nika benchmark run --csv benchmark/benchmark_selected.csv
nika benchmark run -j 4
```

**Default CSV path**: `benchmark/benchmark_selected.csv` under the repository root.

**`-j` / `--parallel`**: run up to N CSV rows concurrently (default `1`). Applies to batch mode only.

**CSV columns** (header row):

| Column | Meaning |
|--------|---------|
| `problem` | Problem id (same as `nika failure inject`) |
| `scenario` | Scenario id (same as `nika env run`) |
| `topo_size` | Tier `s`, `m`, or `l`; **empty** for scenarios without tiers (same values as `nika env run -t`) |

Agent and judge options use the same flags as below (including `-a cli` and `-e` for Codex runs; `-n` applies only to `react` and `mock`).

### Single-case mode

Pass **`SCENARIO`** as the first positional argument (like `nika env run NAME`), plus **`--problem`**:

```shell
nika benchmark run dc_clos_bgp --problem bgp_asn_misconfig -t s \
  -a react -b openai -m gpt-5-mini -n 20 \
  --judge --judge-backend openai --judge-model gpt-5-mini
```

- **`-t` / `--tier`**: required only when `SCENARIO` is scalable.
- **`--judge`**: optional; without it, only metrics and publish run after the agent finishes.
- Each benchmark case gets its own lab; the lab is torn down when the session closes (before evaluation).

---

## `nika traffic`

Requires a deployed lab. By default the **current session** supplies the scenario name (Kathará lab name) and tier; override with **`--lab`** (and **`-t`** when the scenario needs a tier).

- **`nika traffic list`**: supported **`TYPE`** values for `run`.
- **`nika traffic run TYPE …`**: start traffic; options depend on **`TYPE`**.

### Foreground vs background (`--background`)

| TYPE | `--no-background` (default) | `--background` |
|------|------------------------------|------------------|
| `od` | Run iperf3 clients synchronously; print JSON summaries to stdout | Start iperf3 in the background inside the lab; print a short JSON list of flow labels |
| `web` | Block until interrupted or finished (`--no-loop`) | **Not supported** (error): web load always blocks this CLI |

### `nika traffic run od`

OD-matrix iperf3 using `ODFLowGenerator`.

**Exactly one** traffic pattern:

1. **`--od-json PATH`**: JSON object `{ "src_host": { "dst_host": <rate>, ... }, ... }` (rates match `--unit`).
2. **`--mesh-mbps N`**: every ordered pair of distinct hosts in the scenario at `N` Mbit/s (with `--unit M`).
3. **`--all-to-host H --mbps N`**: every host except `H` sends to `H` at `N` Mbit/s (same pattern as bandwidth-throttling examples).

Shared iperf tuning:

- **`--interval`**: iperf `-t` duration (seconds).
- **`--unit`**: `K` or `M` (bitrate suffix for matrix values).
- **`--udp` / `--no-udp`**
- **`--server-args`**, **`--client-args`**: extra iperf3 arguments.

### `nika traffic run web`

Uses `WebBrowsingTrafficGenerator` (ApacheBench against `web_urls`). Only scenarios that define web servers and URLs are valid.

Options:

- **`--request-delay-min`**, **`--request-delay-max`**
- **`--pages-min`**, **`--pages-max`**
- **`--no-loop`**: one browsing session per client host then exit

---

## Helpful paths

- Runtime sessions: `runtime/sessions/*.json` (cleared when a session is finished)
- Eval summary CSV default: `results/0_summary/evaluation_summary.csv`
- Benchmark data: `benchmark/*.csv` under the repo root
