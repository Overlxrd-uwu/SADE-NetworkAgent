# NIKA CLI reference

Entry point: `nika` (see `[project.scripts]` in `pyproject.toml`). During development use `uv run nika …`.

Requires `BASE_DIR` in the environment (or `.env`) pointing at the repository root so runtime and results paths resolve correctly.

## Command tree

| Group | Purpose |
|--------|---------|
| `nika env` | List / deploy Kathará scenarios and create a session |
| `nika failure` | List injectable problems / inject faults for a selected running session |
| `nika agent` | Run a troubleshooting agent on one selected session task |
| `nika eval` | Metrics, LLM judge, session teardown, and offline summary CSV for finished sessions |
| `nika benchmark` | Full pipeline for benchmark CSV rows or a single `(scenario, problem)` case |
| `nika traffic` | Synthetic traffic (`od`, `web`) against the running lab |

Use `nika <group> --help` and `nika <group> <command> --help` for generated option text.

## Global conventions

### Topology tier (`-t` / `--tier`)

Same semantics as `nika env run`:

- **Scalable** scenarios (see `TOPO_SIZE` on lab classes under `src/nika/net_env`) require **`-t s`**, **`-t m`**, or **`-t l`**.
- **Non-scalable** scenarios must **omit** `-t`.

This flag is reused on **`nika benchmark run`** and **`nika traffic run`** when a tier is required and not already implied by the session.

### Agent LLM options

Aligned with `nika agent run`:

- **`-a` / `--agent`**: agent implementation (currently `react`).
- **`-b` / `--backend`**: provider (`openai`, `ollama`, `deepseek`, …).
- **`-m` / `--model`**: model id for that provider.
- **`-n` / `--max-steps`**: ReAct step cap.

`nika eval judge` uses **`-b`** and **`-m`** for the judge only (no agent in that command).

### Benchmark judge options

`nika benchmark run` configures **both** agent and judge in one command, so judge options use a **prefix** to avoid clashing with the agent:

- **`--judge-backend`**
- **`--judge-model`**

---

## `nika env`

- **`nika env list`**: print registered scenario ids.
- **`nika env run NAME [-t s|m|l] [--no-redeploy] [--instance-tag TAG]`**: deploy one instance and persist it in SQLite (`session_id = lab_hash`).
- **`nika env ps`**: list currently running instances (`session_id`, `lab_name`, scenario, tier).
- **`nika env stop [--session-id ID | --all]`**: stop one running instance (auto-select only when exactly one running) or stop all.

---

## `nika failure`

- **`nika failure list`**: injectable problem ids.
- **`nika failure inject PROBLEM [PROBLEM …] [--session-id ID]`**: inject for a selected running session and write ground truth.

---

## `nika agent`

- **`nika agent list`**: supported agent types and backends.
- **`nika agent run [-a react] [-b openai] [-m MODEL] [-n 20] [--session-id ID]`**: run the agent on one selected session.

---

## `nika eval`

- **`nika eval metrics [--session-id ID]`**: rule-based metrics → `eval_metrics.json`.
- **`nika eval judge -b BACKEND -m MODEL [--session-id ID]`**: LLM judge → `llm_judge.json`.
- **`nika eval publish [--no-destroy] [--session-id ID]`**: finalize `run.json`, optionally undeploy, clear runtime session state.
- **`nika eval summary [filters] [-o PATH]`**: scan finished sessions under `results/` and write one CSV.

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

Implements the full end-to-end benchmark pipeline: start env → inject → agent → `eval_results` (metrics + judge + finish). Run `nika eval summary` afterward to aggregate CSV rows across finished sessions.

### Batch mode (default)

Omit the `SCENARIO` positional argument. Rows are read from a CSV file.

```shell
nika benchmark run
nika benchmark run --csv benchmark/benchmark_selected.csv
```

**Default CSV path**: `$BASE_DIR/benchmark/benchmark_selected.csv`.

**CSV columns** (header row):

| Column | Meaning |
|--------|---------|
| `problem` | Problem id (same as `nika failure inject`) |
| `scenario` | Scenario id (same as `nika env run`) |
| `topo_size` | Tier `s`, `m`, or `l`; **empty** for scenarios without tiers (same values as `nika env run -t`) |

Agent, judge, and step options use the same flags as below.

### Single-case mode

Pass **`SCENARIO`** as the first positional argument (like `nika env run NAME`), plus **`--problem`**:

```shell
nika benchmark run dc_clos_bgp --problem bgp_asn_misconfig -t s \
  -a react -b openai -m gpt-5-mini -n 20 \
  --judge-backend openai --judge-model gpt-5-mini \
  --destroy-env
```

- **`-t` / `--tier`**: required only when `SCENARIO` is scalable.
- **`--destroy-env` / `--no-destroy-env`**: whether to tear down the lab after evaluation (default: `--no-destroy-env`).

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

- Runtime sessions: `$BASE_DIR/runtime/sessions/*.json` (cleared when a session is finished)
- Eval summary CSV default: `$BASE_DIR/results/0_summary/evaluation_summary.csv`
- Benchmark data: `benchmark/*.csv` under the repo root
