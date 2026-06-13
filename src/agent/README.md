# Agent Architecture

`src/agent` hosts multiple troubleshooting agent implementations for NIKA. All implementations share the same entry contract (`protocols.TroubleshootingAgent`) and produce the same session artifacts (`messages.jsonl`, `submission.json`, etc.).

## Directory Layout

```
src/agent/
├── protocols.py          # Shared Protocol interface
├── registry.py           # Type registry and factory for `nika agent run`
├── langgraph/            # [implemented] LangGraph + LangChain ReAct
│   ├── react_agent.py    # StateGraph orchestration: diagnosis → submission
│   └── domain_agents/    # LangChain create_agent subgraphs
├── mock/                 # [implemented] Deterministic mock without an LLM
│   └── mock_agent.py
├── sdk/                  # [planned] Direct Claude / Codex SDK integration
│   └── agent.py
├── cli/                  # [implemented] LangGraph + Codex CLI
│   ├── agent.py          # CliAgent — StateGraph orchestrator
│   ├── codex_worker.py   # CodexWorker — codex exec subprocess adapter
│   ├── codex_display.py  # Terminal formatting for codex --json events
│   └── domain_agents/    # Per-phase Codex CLI workers (diagnosis / submission)
├── llm/                  # LangChain model factory for the LangGraph path
│   └── model_factory.py
└── utils/                # Shared utilities across implementations
    ├── mcp_servers.py    # Kathara / task MCP configuration
    └── loggers.py        # Structured logging to messages.jsonl
```

## Four Implementation Paths

| Type | CLI name | Orchestration | LLM access | Status |
|------|----------|---------------|------------|--------|
| LangGraph | `react` | LangGraph `StateGraph` | LangChain ReAct + `load_model()` | Implemented |
| Mock | `mock` | Hand-written two-phase flow | No LLM; fixed tool sequence | Implemented |
| SDK | `sdk` | TBD (recommended: same two phases) | Anthropic SDK / Cursor SDK | Planned |
| LangGraph + CLI | `cli` | LangGraph `StateGraph` | `codex exec` subprocess | Implemented |

## Shared Two-Phase Flow

Every implementation follows the same troubleshooting pipeline:

```mermaid
flowchart LR
    Task[task_description] --> Diagnosis[diagnosis_agent]
    Diagnosis -->|diagnosis_report| Submission[submission_agent]
    Submission --> Done[submission.json]

    subgraph diagnosis_tools [Diagnosis MCP]
        Kathara[kathara_* servers]
    end

    subgraph submission_tools [Submission MCP]
        TaskMCP[task_mcp_server]
    end

    Diagnosis --> diagnosis_tools
    Submission --> submission_tools
```

- **Diagnosis**: Connects to Kathara MCP servers (`if_submit=False`) to detect anomalies, localize faulty devices, and identify root causes.
- **Submission**: Connects to the task MCP server (`if_submit=True`) and calls `list_avail_problems` + `submit`.

## 1. LangGraph Path (`-a react`)

**Entry point**: `agent.langgraph.react_agent.BasicReActAgent`

- Top-level orchestration uses a LangGraph `StateGraph` with two nodes.
- Each node is a LangChain `create_agent` ReAct subgraph (`DiagnosisAgent` / `SubmissionAgent`).
- LLMs are loaded via `agent.llm.model_factory.load_model()` (openai / ollama / deepseek).
- Tracing: Langfuse + LangSmith. Logging: `AgentCallbackLogger`.

```bash
nika agent run -a react -b openai -m gpt-5-mini -n 20
nika agent run -a react -b deepseek -m deepseek-chat -n 20
```

## 2. Mock Path (`-a mock`)

**Entry point**: `agent.mock.mock_agent.MockAgent`

- Skips LangGraph and LangChain; calls MCP tools from a fixed script.
- Matches the `BasicReActAgent.run()` interface for CI and parallel benchmark tests.
- Writes the same `messages.jsonl` event schema as the LangGraph path.

```bash
nika agent run -a mock -n 5
```

## 3. SDK Path (`-a sdk`, planned)

**Placeholder**: `agent.sdk.agent.SdkAgent`

Design notes:

- Bypass LangChain and use Claude / Codex SDK tool-use APIs directly.
- Expose MCP tools to the model via SDK MCP configuration or an adapter.
- Keep the diagnosis → submission flow and the same logging format.

Register the `"sdk"` branch in `registry.create_agent()` once implemented.

## 4. LangGraph + CLI Path (`-a cli`)

**Entry point**: `agent.cli.agent.CliAgent`

- Mirrors the same two-node `StateGraph` structure as `BasicReActAgent` (implemented in `cli/agent.py`).
- Replaces LangChain workers with `CodexWorker` subprocess wrappers (`codex exec`).
- Each phase runs in an isolated per-session workspace under `results/{session_id}/codex_workspace/`.
- MCP servers are written to a private `CODEX_HOME` so the global `~/.codex/` config is not touched.
- `codex exec --json` events are streamed line-by-line to `messages.jsonl` and pretty-printed to the terminal.

```bash
# authenticate once
codex login

nika agent run -a cli -m gpt-5.4-mini -e medium
```

The `-b` / `--backend` flag applies to ``react`` and ``mock`` only; Codex CLI always uses OpenAI models.
Use `-e` / `--reasoning-effort` to set Codex ``model_reasoning_effort`` (``none``, ``minimal``, ``low``, ``medium``, ``high``, ``xhigh``).

## Example Workflow

```bash
nika env run simple_bgp
nika failure inject link_down --set host_name=pc1 --set intf_name=eth0
nika agent run -a cli -m gpt-5.4-mini
nika session close -y
nika eval metrics
```

See the root [README.md](../../README.md#troubleshooting-agents) for a longer walkthrough including ReAct and evaluation steps.

## Adding a New Agent

1. Implement a class in the appropriate subpackage with `async def run(task_description) -> dict`.
2. Add a branch in `registry.create_agent()`.
3. Ensure `MessageLogger` (or `AgentCallbackLogger` for LangChain paths) writes to `{session_dir}/messages.jsonl`.

## CLI Usage

```bash
nika agent list                              # List agent types and LLM backends
nika agent run -a react -b openai -m ...   # LangGraph path
nika agent run -a cli -m gpt-5.4-mini      # Codex CLI path
nika agent run -a mock                       # Mock path (no LLM required)
# nika agent run -a sdk                      # Not yet implemented
```

Registration and dispatch live in `nika/workflows/agent/run.py` → `agent.registry.create_agent()`.
