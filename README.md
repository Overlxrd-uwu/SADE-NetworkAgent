<div align="center">
<h1>A Network Arena for Benchmarking AI Agents on Network Troubleshooting</h1>

[🤖Overview](#🤖overview) | 
[📦Installation](#📦installation) | 
[🚀Quick Start](#🚀quick-start) | 
[🛠️Usage](#🛠️usage) | 
[📚Cite](#📚cite)

[![ArXiv Link](https://img.shields.io/badge/arXiv-2512.16381-red?logo=arxiv)](https://arxiv.org/abs/2512.16381)

</div>

<h1 id="🤖overview">🤖 Overview</h1>

![alt text](./assets/images/nika_arch_gpt.png)

This repository is a unified platform that can offer: 
1. A benchmark suite of curated network incidents that covers 54 realistic network issues, ranging from link and host failures to resource contention, and includes five network scenarios, four of which can be instantiated at different topology sizes, spanning campus and data center networks. By combining these dimensions, the benchmark yields 640 distinct troubleshooting incidents for evaluating AI agents. The benchmark can be further extended by randomizing failure locations and composing multiple issues within a single incident. 
2. A modular plug-and-play orchestration platform that connects AI agents with the network environment, enabling real-time troubleshooting in realistic conditions, and providing a human-facing interface to monitor agent performance.


💡 **Note:** We are actively developing this framework. If you have any suggestions or are interested in contributing, feel free to reach out to us!

## Features

- Standardized network troubleshooting environment based on Kathará
- Unified `nika` CLI for env deploy, fault injection, agent runs, and evaluation
- Session-based workflow with multi-session support (`nika session`, `--session-id`)
- Parameterized fault injection (`nika failure describe`, `--set key=value`)
- MCP-based tool support
- Pre-built network scenarios and fault injection mechanisms
- Reproducible evaluation framework with batch summary (`nika eval summary`)
- Support for various network topologies and configurations
- Easy integration of custom AI agents
- Automatic evaluation mechanism

<h1 id="📦installation">📦 Installation</h1>

## Requirements

- [Kathará](https://www.kathara.org/). 
  Follow the [official installation guide](https://github.com/KatharaFramework/Kathara?tab=readme-ov-file#installation) to install Kathará.
- Python >= 3.12


## Setup

Clone the repository and install the dependencies. 
NIKA uses [uv](https://docs.astral.sh/uv) to manage the dependencies. Follow [uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/) to install uv. You can also use a standard `pip install -e .` to install the dependencies.

```shell
# Clone the repository
git clone https://github.com/sands-lab/nika
cd nika

# Install dependencies
uv sync

# Activate the environment
source .venv/bin/activate
```

The Kathará API relies on Docker to function properly. We recommend to add current user to docker group to avoid calling with `sudo`. **However, please be aware of the security implications of this action.**

```shell
sudo usermod -aG docker $USER
```

Login again or activate temporaily with 

```shell
newgrp docker
```

<h1 id="🚀quick-start">🚀 Quick Start</h1>

## Configure environment variables

Create a `.env` file under the base directory and set the following environment variables:

```shell
# if use Langsmith for observability
# check langsmith documentation for more details
LANGSMITH_TRACING="true"
LANGSMITH_ENDPOINT=<>
LANGSMITH_API_KEY=<>
LANGSMITH_PROJECT=<>

# if use langfuse for observability
# check langfuse documentation for more details
LANGFUSE_SECRET_KEY=<>
LANGFUSE_PUBLIC_KEY=<>
LANGFUSE_HOST="https://cloud.langfuse.com"

# api key for you LLM, e.g. DeepSeek here
DEEPSEEK_API_KEY=<>
OPENAI_API_KEY=<>

# if use ollama for llm 
OLLAMA_API_URL=<>
```

## Step by step guide
You can follow the steps below to run a complete troubleshooting task with NIKA. Use the `nika` CLI.

Each `nika env run` creates a **session** (printed as `session_id=…`). Session state lives under `runtime/sessions/` and tracks the deployed lab, injected failures, and agent activity. When only one session is running, most commands auto-select it; pass `--session-id` when several sessions are active.

1. **List scenarios and start the network environment**

   ```shell
   nika env list
   nika env run <scenario>                    # scenarios without topology tiers (e.g. simple_bgp)
   nika env run <scenario> -t s             # scalable scenarios (tier: s, m, or l)
   nika env ps                                # running lab instances (grouped by deployed env)
   ```

2. **Inspect and manage sessions**

   ```shell
   nika session ps                            # running sessions (status, failures, agents)
   nika session ps -a                         # include finished sessions
   nika session inspect [SESSION_ID]          # full session JSON + failure summary
   nika session close [SESSION_ID]            # undeploy lab and clear runtime state
   nika session close all -y                  # close every running session
   ```

3. **List problems and inject faults**

   ```shell
   nika failure list
   nika failure describe <problem_id>         # parameter schema and usage hints
   nika failure inject <problem_id> [<problem_id> ...]
   nika failure inject link_down --set host_name=pc1 --set intf_name=eth0
   nika failure ps [--session-id ID]          # persisted injection records
   ```

4. **Run commands inside a lab host** (optional debugging)

   ```shell
   nika exec pc1 ip addr show
   nika exec pc1 ping -c 3 10.0.0.2 --timeout 30
   ```

5. **List agent options and run the agent**

   ```shell
   nika agent list
   nika agent run -a react -b openai -m gpt-5-mini -n 20   # LangGraph + LangChain ReAct
   nika agent run -a cli -m gpt-5.4-mini                    # Codex CLI subprocess worker
   nika agent run -a cli -m gpt-5.4-mini -e medium        # optional Codex reasoning effort
   nika agent run -a mock -n 5                             # no LLM; useful for pipeline testing
   ```

   See **[Troubleshooting Agents](#troubleshooting-agents)** below for architecture notes and a full walkthrough example.

6. **Close the session, then evaluate the run** (metrics, judge, publish, and CSV summary are separate steps)

   ```shell
   nika session close [SESSION_ID] -y           # undeploy lab and clear runtime state first
   nika eval metrics
   nika eval judge -b openai -m gpt-5-mini
   nika eval publish
   nika eval summary                              # all finished sessions → default CSV
   nika eval summary -p link_down -e simple_bgp   # filter by problem and scenario
   nika eval summary -o results/0_summary/my_run.csv
   ```

Full CLI documentation (benchmark batch mode, traffic types, parameter tables, and conventions) lives in **[src/nika/codex_cli/README.md](src/nika/codex_cli/README.md)**.

### Optional: benchmark or traffic from the CLI

```shell
nika benchmark run
nika benchmark run dc_clos_bgp --problem bgp_asn_misconfig -t s
nika benchmark run --judge --judge-backend openai --judge-model gpt-5-mini
nika traffic list
nika traffic run od --all-to-host pc1 --mbps 20 --interval 300 --background
```

## Run Unit Tests

```shell
# run all unit tests
uv run --with pytest pytest

# verbose output
uv run --with pytest pytest -v

# run only selected test files
uv run --with pytest pytest tests/test_session.py -v
```

<h1 id="🛠️usage">🛠️ Usage</h1>

## Troubleshooting Agents

Agent implementations live under [`src/agent/`](src/agent/). For architecture, directory layout, and extension notes, see **[src/agent/README.md](src/agent/README.md)**.

NIKA ships two LLM-backed agents for real troubleshooting runs, plus a deterministic mock for CI:

| Agent | CLI flag | How it works | Prerequisites |
| ----- | -------- | ------------ | ------------- |
| **ReAct** | `-a react` | LangGraph orchestrates two LangChain ReAct workers (diagnosis → submission) | LLM API key in `.env` (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, or Ollama URL) |
| **Codex CLI** | `-a cli` | Same two-phase LangGraph flow, but each phase runs `codex exec` as a subprocess with Kathara MCP servers | [Codex CLI](https://developers.openai.com/codex) installed and authenticated (`codex login` or `OPENAI_API_KEY`) |
| **Mock** | `-a mock` | Fixed tool-call script; no LLM | None |

Both LLM agents (and the mock agent) write structured traces to `results/{session_id}/messages.jsonl` and produce `submission.json` via the task MCP server.

### ReAct agent (`-a react`)

```shell
nika agent list
nika agent run -a react -b openai -m gpt-5-mini -n 20
nika agent run -a react -b deepseek -m deepseek-chat -n 20
```

- **`-b` / `--backend`**: `openai`, `ollama`, or `deepseek`
- **`-m` / `--model`**: model id for the chosen backend
- **`-n` / `--max-steps`**: max ReAct recursion steps per phase
- Tracing: Langfuse + LangSmith (configure keys in `.env`)

### Codex CLI agent (`-a cli`)

Requires [Codex CLI](https://developers.openai.com/codex); follow the [official installation guide](https://developers.openai.com/codex/quickstart) to install and authenticate.

```shell
# authenticate once
codex login

# run on the current session task
nika agent run -a cli -m gpt-5.4-mini
```

- Uses `codex exec --json` under the hood; reasoning steps stream to the terminal in real time (MCP tool calls, agent messages, turn progress) and are logged to `messages.jsonl`.
- The `-b` backend flag is accepted for CLI parity but ignored — Codex always uses OpenAI models.
- **`-e` / `--reasoning-effort`**: Codex `model_reasoning_effort` (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`).
- Per-session Codex workspace: `results/{session_id}/codex_workspace/`

See **[src/nika/codex_cli/README.md](src/nika/codex_cli/README.md)** for full `nika agent` flags and conventions.

### Example: `simple_bgp` with `link_down`

End-to-end workflow from lab deploy through agent run and evaluation:

```shell
# 1. Deploy the network environment (creates a session)
nika env list
nika env run simple_bgp
# → prints session_id=20260613-061340-072e35

# 2. Inspect the fault schema, then inject a link-down on pc1
nika failure describe link_down
nika failure inject link_down --set host_name=pc1 --set intf_name=eth0

# 3. (optional) verify the fault from inside the lab
nika exec pc1 ip link show eth0
nika exec pc2 ping -c 3 195.11.14.2

# 4. Run a troubleshooting agent on the session task
# Option A — LangGraph + LangChain ReAct
nika agent run -a react -b openai -m gpt-5-mini -n 20

# Option B — Codex CLI (streams step-by-step output to the terminal)
nika agent run -a cli -m gpt-5.4-mini

# 5. Inspect session state and artifacts
nika session inspect
ls results/<session_id>/
# run.json, ground_truth.json, events.jsonl, messages.jsonl, submission.json, codex_workspace/ (cli only)

# 6. Close the lab, then evaluate
nika session close -y
nika eval metrics
nika eval judge -b openai -m gpt-5-mini
nika eval publish
```

When multiple sessions are running, pass `--session-id <id>` to `failure inject`, `agent run`, and other session-scoped commands.

## Network Scenarios

Registered scenarios (see `nika env list`) live under `src/nika/net_env/`:

| Scenario ID | Scalable | Description |
| ----------- | -------- | ----------- |
| `dc_clos_bgp` | ✓ | Multi-tier data center CLOS with EBGP (FRR). |
| `dc_clos_service` | ✓ | Data center CLOS with DNS/HTTP edge services and external clients. |
| `ospf_enterprise_static` | ✓ | Enterprise hierarchical OSPF network with static host addressing. |
| `ospf_enterprise_dhcp` | ✓ | Enterprise OSPF network with DHCP for host addressing. |
| `rip_small_internet_vpn` | ✓ | Small RIP-based Internet with external zones and WireGuard VPN overlay. |
| `sdn_clos` | ✓ | Scalable SDN spine–leaf fabric with OpenFlow controller. |
| `sdn_star` | ✓ | SDN star (hub-and-spoke) topology with OpenFlow controller. |
| `simple_bgp` | -- | Compact inter-domain BGP lab (two routers, two hosts). |
| `p4_int` | -- | P4 spine–leaf testbed with In-band Network Telemetry (InfluxDB). |
| `p4_bloom_filter` | -- | P4 bloom-filter data-plane validation testbed. |
| `p4_counter` | -- | P4 counter pipeline testbed. |
| `p4_mpls` | -- | P4 MPLS data-plane testbed. |


💡 More scenarios are WIP!

Each scenario is defined in a Kathará `lab.py` file, which specifies the network topology, devices, and initial configurations. Check [Kathará API Docs](https://github.com/KatharaFramework/Kathara/wiki/Kathara-API-Docs) for more details if you want to create your scenarios.

## Network issues

This framework provides a set of predefined issues that can be injected into the network environment. These issues are categorized into different types, each with specific root causes and key signals. By combining the issues with the network scenarios, randomlizing the failure locations, and composing multiple issues, this framework can generate multiple incidents based on a network issue (see # Incident column).
The following table summarizes the issues available in this framework:

| Category                               | Root Cause                              | Key Signals                                                     | # Incident |
| -------------------------------------- | --------------------------------------- | --------------------------------------------------------------- | ---------- |
| Link failures                          | Link flap                               | Flap event logs; packet drops                                   | 26         |
| Link failures                          | Link detached                           | Physical link not detected; PHY down                            | 26         |
| Link failures                          | Link down                               | Interface state down                                            | 26         |
| Link failures                          | Faulty cable                            | CRC errors; corrupted frames                                    | 26         |
| Link failures                          | MAC address conflict                    | Same MAC seen on multiple ports; MAC flapping logs              | 26         |
| Link failures                          | Link fragmentation disabled             | Large packets dropped; MTU mismatch                             | 26         |
| End-host failures                      | Conflicting VPN memberships             | Overlapping subnets; VPN servers unreachable                    | 3          |
| End-host failures                      | Host crash                              | Host unresponsive; no heartbeat; ping fails                     | 35         |
| End-host failures                      | Host IP conflict                        | Duplicate IP alerts; ARP conflict detected                      | 26         |
| End-host failures                      | Host IP misconfig                       | Incorrect or missing IP address; host unresponsive              | 68         |
| End-host failures                      | Incorrect netmask                       | Partial reachability; inconsistent routing behavior             | 16         |
| End-host failures                      | DNS empty answer                        | Incorrect or missing DNS records; NXDOMAIN                      | 6          |
| Network node errors                    | Number of MPLS labels hit limit         | Error logs; packet drops                                        | 1          |
| Network node errors                    | Switch/router crash (e.g., overheating) | Switch down and unreachable from MGMT                           | 20         |
| Network node errors                    | P4 program reads `invalid` header field | Packet drops; error logs (platform-dependent)                   | 8          |
| Network node errors                    | SDN controller crash                    | Switches isolated; new flows dropped                            | 6          |
| Network node errors                    | Southbound port unreachable             | OpenFlow/TCP 6633/6653 unreachable                              | 12         |
| Misconfigurations (routing, ACL, etc.) | BGP ASN mismatch                        | BGP session fails; ASN mismatch detected                        | 7          |
| Misconfigurations (routing, ACL, etc.) | BGP blackhole route leak                | Traffic to specific prefixes blackholed; unexpected AS path     | 7          |
| Misconfigurations (routing, ACL, etc.) | Missing BGP advertisement               | Prefix not propagated; missing announcements                    | 7          |
| Misconfigurations (routing, ACL, etc.) | Host static blackhole                   | Static blackhole route active; traffic dropped                  | 7          |
| Misconfigurations (routing, ACL, etc.) | OSPF area misconfiguration              | OSPF adjacency failure; area mismatch                           | 6          |
| Misconfigurations (routing, ACL, etc.) | OSPF neighbor missing                   | Missing neighbor; no Hello packets exchanged                    | 6          |
| Misconfigurations (routing, ACL, etc.) | Forwarding table entry misconfig        | No matching entry; default drop                                 | 8          |
| Misconfigurations (routing, ACL, etc.) | Flow rule loop                          | Traffic loop observed; CPU spike; port flooding                 | 6          |
| Misconfigurations (routing, ACL, etc.) | Flow rule shadowing                     | Lower-priority rule overridden by higher-priority rule          | 6          |
| Misconfigurations (routing, ACL, etc.) | ARP ACL block                           | ARP requests or replies dropped; ACL deny counters increase     | 26         |
| Misconfigurations (routing, ACL, etc.) | ICMP ACL block                          | ICMP traffic blocked; ping fails                                | 26         |
| Misconfigurations (routing, ACL, etc.) | Routing control-plane ACL block         | BGP (TCP/179) or OSPF (IP proto 89) blocked; neighborship fails | 13         |
| Misconfigurations (routing, ACL, etc.) | HTTP ACL block                          | HTTP 80/443 traffic blocked; client connection timeout          | 12         |
| Resource contention                    | Microbursts on interface                | Reduced throughput; queue buildup                               | 26         |
| Resource contention                    | Receiver saturated & slow               | Multiple segments ACKed per ACK; RWND < CWND                    | 12         |
| Resource contention                    | Incast traffic                          | Queue buildup; packet drops; retransmissions                    | 12         |
| Resource contention                    | Sender saturated & slow                 | Segments smaller than MSS; Flight size < min(CWND,RWND)         | 24         |
| Resource contention                    | Software middle-box overloads           | CPU usage saturates; queue buildup; RTT increases               | 3          |
| Network under attack                   | Service DoS                             | Surge in HTTP connections; CPU/RAM usage spikes                 | 18         |
| Network under attack                   | BGP hijacking                           | More specific or illegitimate prefixes appear; path anomaly     | 3          |
| Network under attack                   | DHCP spoofing                           | DHCP clients received spoofed configurations (IP, DNS, etc.)    | 9          |
| Network under attack                   | DNS spoofing                            | DNS points to wrong addresses                                   | 12         |
| Network under attack                   | ARP cache poisoning                     | Abnormal traffic redirection                                    | 26         |
| Network under attack                   | Misaligned sketch thresholds            | False-positive cardinality alerts (e.g., DoS); packet drops     | 1          |
| **Total**                              | -                                       | -                                                               | **640**    |

Based on the above issues, we disclose a large public dataset of AI agents’ behavior for network troubleshooting, with more than 900 reasoning traces. See the [![Zenodo Dataset](https://img.shields.io/badge/Zenodo-17971675-blue?logo=zenodo)](https://zenodo.org/records/17971675).

## MCP Servers and Tools

This framework provides MCP servers under `src/nika/service/mcp_server`. These include:

- **Kathará base MCP server** (`kathara_base_mcp_server.py`): host reachability and diagnostics, including
  - `get_reachability` to ping all pairs of hosts (subset when the lab is large).
  - `ping_pair` to ping between two specific hosts.
  - `iperf_test` to run an iperf test between two hosts.
  - `systemctl_ops` to manage system services (start, stop, restart, status).
  - `get_host_net_config` to retrieve the network configuration of a host.
  - `get_tc_statistics`, `netstat`, `ip_addr_statistics`, `ethtool`, `curl_web_test` for interface and service checks.
  - `cat_file`, `exec_shell`, `exec_shell_dual` to read files or run commands in containers.
- **BMv2 MCP server** (`kathara_bmv2_mcp_server.py`): P4/BMv2 switch interaction, including
  - `bmv2_get_log`, `bmv2_get_counter_arrays`, `bmv2_read_p4_program`, `bmv2_counter_read`.
  - `bmv2_show_tables`, `bmv2_table_dump`, `bmv2_get_register_arrays`, `bmv2_register_read`.
- **FRR MCP server** (`kathara_frr_mcp_server.py`): FRRouting routers, including
  - `frr_get_bgp_conf`, `frr_get_ospf_conf`, `frr_show_running_config`, `frr_show_ip_route`, `frr_exec`.
- **Telemetry MCP server** (`kathara_telemetry_mcp_server.py`): INT/InfluxDB telemetry, including
  - `influx_list_buckets`, `influx_get_measurements`, `influx_count_measurements`, `influx_query_measurement`.
- **Task management MCP server** (`task_mcp_server.py`): agent submissions, including
  - `list_avail_problems` to list injectable root-cause ids.
  - `submit` to write the agent's final detection/localization/RCA answer.

💡 More tools are coming soon...

You can also plug in your own MCP servers following the configuration instruction. Look for more MCP servers at [mcp.so](https://mcp.so/).



## Logging and Observability

The built-in ReAct agent (`react`) traces runs with **Langfuse** (LangChain `CallbackHandler`) and **LangSmith** (`langsmith.tracing_context`). The Codex CLI agent (`cli`) streams `codex exec --json` events to the terminal and logs them to `messages.jsonl` in real time. Configure observability keys in `.env` as shown above. See [LangChain Callbacks](https://python.langchain.com/docs/concepts/callbacks/) for callback details.

Each session directory under `results/{session_id}/` also contains:

- **`events.jsonl`**: pipeline/system events from `nika.utils.logger` (env deploy, fault inject, agent start/end, eval).
- **`messages.jsonl`**: agent conversation and tool traces from `src/agent/utils/loggers.py`.

### Customized Logger

Agent message logging is built on `MessageLogger` in `src/agent/utils/loggers.py`, which writes structured JSONL to `{session_dir}/messages.jsonl`. The LangGraph ReAct path wraps it with `AgentCallbackLogger` (a LangChain `BaseCallbackHandler`); the Codex CLI path calls `MessageLogger` directly from `CodexWorker`. To extend the ReAct path:

```python
from agent.utils.loggers import AgentCallbackLogger

callback = AgentCallbackLogger(agent="diagnosis_agent", session_dir=session_dir)
result = await agent.ainvoke(
    {"messages": messages},
    config={"callbacks": [callback]},
)
```

<h1 id="📚cite">📚 Cite</h1>

```bibtex
@misc{nika,
      title={A Network Arena for Benchmarking AI Agents on Network Troubleshooting}, 
      author={Zhihao Wang and Alessandro Cornacchia and Alessio Sacco and Franco Galante and Marco Canini and Dingde Jiang},
      year={2025},
      eprint={2512.16381},
      archivePrefix={arXiv},
      primaryClass={cs.NI},
      url={https://arxiv.org/abs/2512.16381}, 
}
```

```bibtex
@inproceedings{llm4netlab,
author = {Wang, Zhihao and Cornacchia, Alessandro and Galante, Franco and Centofanti, Carlo and Sacco, Alessio and Jiang, Dingde},
title = {Towards a Playground to Democratize Experimentation and Benchmarking of AI Agents for Network Troubleshooting},
year = {2025},
isbn = {9798400720871},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3748496.3748990},
doi = {10.1145/3748496.3748990},
booktitle = {Proceedings of the 1st Workshop on Next-Generation Network Observability},
pages = {1–3},
numpages = {3},
location = {Coimbra, Portugal},
series = {NGNO '25}
}
```

# Acknowledgement

This project is largely motivated by [AIOpsLab](https://github.com/microsoft/AIOpsLab). We sincerely thank the authors for their excellent work.

# Licence

Licensed under the MIT license.