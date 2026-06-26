"""SADE community agent — Symptom-Aware Diagnostic Escalation over Claude Code.

Implements the ``agent.protocols.TroubleshootingAgent`` contract
(``session_id`` + ``async def run(task_description) -> dict``) and is selected
via ``nika agent run -a sade``.

Unlike the LangGraph paths, SADE drives a single Claude Code session
(``claude-agent-sdk``) with a phase-gated system prompt and a 15-skill library
loaded from this package's ``.claude/`` directory. It still produces the same
diagnosis -> submission outcome through NIKA's Kathara + task MCP servers, and
writes structured events to the session's ``messages.jsonl`` in the schema the
NIKA trace parser/evaluator expects.

Reference: SADE (arXiv:2605.04530), built on NIKA.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from dotenv import load_dotenv

from agent.utils.loggers import AgentCallbackLogger
from agent.utils.mcp_servers import MCPServerConfig
from nika.utils.logger import system_logger
from nika.utils.session import Session

from .prompts.sade_prompt import SADE_PROMPT

load_dotenv()

# Directory holding this agent's `.claude/` skill library, `CLAUDE.md`, and the
# `h.py` helper launcher. The Claude Code SDK uses it as the working directory
# so skills and helpers resolve with simple relative paths (`python h.py ...`).
PACKAGE_DIR = Path(__file__).resolve().parent

# The NIKA trace parser derives token/step counts from the diagnosis agent
# (``agent_filter="diagnosis_agent"``); SADE does diagnosis + submission in one
# Claude Code session, so it tags its events with this name.
AGENT_TAG = "diagnosis_agent"

# Fraction of the turn budget at which a single workflow reminder is injected.
TURN_REMINDER_FRAC = 0.50

SADE_REMINDER = (
    "SADE REMINDER: API turn {turn}/{total} ({remaining} remaining). "
    "If direct evidence on the owning device already matches a fault-family "
    "fingerprint, submit NOW — do not hypothesize secondary mechanisms the "
    "topology does not support. If you have a symptom but no owner yet, stay "
    "on that lead and stop broad probing. If you still have no symptom, do one "
    "broad lower-to-higher-layer escalation sweep, then submit `is_anomaly=False` "
    "only if that sweep finds nothing. Check the submit() signature in CLAUDE.md "
    "before calling — wrong types end the session."
)


def _require_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to the repo-root .env or "
            "export it before running `nika agent run -a sade`."
        )
    return api_key


def _resolve_python() -> str:
    """Interpreter used to spawn the stdio MCP servers.

    NIKA's ``MCPServerConfig`` hardcodes ``python3`` (absent on native
    Windows). The SDK spawns these servers on the host, so prefer the
    interpreter currently running NIKA — it is guaranteed to exist and to
    have the ``nika`` package importable.
    """
    return sys.executable or "python3"


def _to_sdk_mcp_servers(config: dict[str, Any]) -> dict[str, Any]:
    """Adapt NIKA's MultiServerMCPClient config to claude-agent-sdk stdio format.

    NIKA returns ``{"transport": "stdio", "command": ..., "args": ...}`` (the
    langchain-mcp-adapters shape); claude-agent-sdk expects
    ``{"type": "stdio", "command": ..., "args": ..., "env": ...}``.
    """
    servers: dict[str, Any] = {}
    for name, spec in config.items():
        command = spec.get("command")
        if command in ("python3", "python"):
            command = _resolve_python()
        servers[name] = {
            "type": "stdio",
            "command": command,
            "args": list(spec.get("args", [])),
            "env": dict(spec.get("env", {})),
        }
    return servers


def _usage_metadata(usage: dict[str, Any] | None) -> dict[str, int]:
    """Map an Anthropic per-turn usage dict to the langchain-style fields the
    NIKA trace parser reads from ``llm_end`` (``usage_metadata.input_tokens`` /
    ``output_tokens``). Input counts cached + uncached prompt tokens.
    """
    u = usage or {}
    return {
        "input_tokens": (
            u.get("input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
        ),
        "output_tokens": u.get("output_tokens", 0),
    }


class SadeAgent:
    """SADE: phase-gated Claude Code agent with the 15-skill library.

    Implements ``agent.protocols.TroubleshootingAgent``. Diagnosis and
    submission run inside a single Claude Code session: diagnosis tools come
    from the Kathara MCP servers, submission via the task MCP server's
    ``submit`` tool. Structured events are written to ``messages.jsonl``.
    """

    def __init__(
        self,
        session_id: str,
        llm_backend: str = "claude",
        model: str = "claude-sonnet-4-6",
        max_steps: int = 20,
        **_: Any,
    ) -> None:
        self.session_id = session_id
        self.llm_backend = llm_backend
        self.model = model
        self.max_steps = max_steps
        self.session = Session()
        self.session.load_running_session(session_id=session_id)

        mcp = MCPServerConfig(session_id=session_id)
        merged = {**mcp.load_config(if_submit=False), **mcp.load_config(if_submit=True)}
        self.mcp_servers = _to_sdk_mcp_servers(merged)

    async def run(self, task_description: str) -> dict[str, Any]:
        api_key = _require_api_key()
        logger = AgentCallbackLogger(agent=AGENT_TAG, session_dir=self.session.session_dir)
        system_logger.info(f"sade: starting session {self.session_id}")

        options = ClaudeAgentOptions(
            system_prompt=SADE_PROMPT,
            model=self.model,
            cwd=str(PACKAGE_DIR),
            mcp_servers=self.mcp_servers,
            max_turns=self.max_steps,
            permission_mode="bypassPermissions",
            # Exposes this package's `.claude/` skill library + CLAUDE.md.
            setting_sources=["project"],
            env={
                "ANTHROPIC_API_KEY": api_key,
                "ANTHROPIC_AUTH_TOKEN": "",
                # Lets `h.py` (spawned from the Bash tool, outside the MCP
                # launch context) resolve the running lab for LAB_NAME.
                "NIKA_SESSION_ID": self.session_id,
            },
        )

        logger._log(
            "llm_start",
            {
                "messages": {"role": "user", "content": task_description},
                "model": {"name": self.model, "backend": self.llm_backend},
                "mcp_servers": list(self.mcp_servers.keys()),
            },
        )

        result_text = ""
        api_turn_count = 0
        reminded = False
        has_submitted = False
        reminder_at = int(self.max_steps * TURN_REMINDER_FRAC)
        in_tokens = 0
        out_tokens = 0
        turn_text: list[str] = []

        def _flush_turn() -> None:
            """Emit the accumulated assistant turn as one canonical ``llm_end``.

            NIKA's parser counts ``llm_end`` events as steps and the LLM judge
            reads ``text`` as the agent's response, so each turn's reasoning is
            emitted here. Token usage is reported once at the ResultMessage:
            per-message SDK usage is a streamed partial that repeats across a
            turn and would mis-sum.
            """
            nonlocal turn_text
            if turn_text:
                logger._log("llm_end", {"text": "\n".join(turn_text), "usage_metadata": {}})
                turn_text = []

        async with ClaudeSDKClient(options=options) as client:
            await client.query(task_description)
            async for message in client.receive_messages():
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    system_logger.info(f"sade: session started - {message.data.get('session_id')}")
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            api_turn_count += 1
                            turn_text.append(block.thinking)
                        elif isinstance(block, TextBlock):
                            turn_text.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            # Emit the reasoning that led to this call, then the
                            # tool call (llm_end -> tool_start order, like NIKA).
                            _flush_turn()
                            logger._log(
                                "tool_start",
                                {"tool": {"name": block.name}, "input": str(block.input)},
                            )
                            if "submit" in block.name:
                                has_submitted = True
                elif isinstance(message, UserMessage):
                    _flush_turn()  # close the turn that called these tools
                    content = message.content if isinstance(message.content, list) else []
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            if block.is_error:
                                logger._log("tool_error", {"output": str(block.content)})
                            else:
                                logger._log(
                                    "tool_end",
                                    {"output": str(block.content), "output_type": "tool_result"},
                                )
                    if not reminded and not has_submitted and api_turn_count >= reminder_at:
                        reminded = True
                        remaining = self.max_steps - api_turn_count
                        text = SADE_REMINDER.format(
                            turn=api_turn_count, total=self.max_steps, remaining=remaining
                        )
                        await client.query(text)
                        system_logger.info(
                            f"sade: REMINDER at API turn {api_turn_count}/{self.max_steps}"
                        )
                elif isinstance(message, ResultMessage):
                    _flush_turn()  # flush any trailing assistant text
                    result_text = message.result or ""
                    md = _usage_metadata(message.usage)
                    in_tokens = md["input_tokens"]
                    out_tokens = md["output_tokens"]
                    # Final `llm_end`: the agent's result text + the authoritative
                    # cumulative token usage (the parser sums usage_metadata).
                    logger._log("llm_end", {"text": result_text, "usage_metadata": md})
                    system_logger.info(
                        f"sade: session complete - stop_reason={message.stop_reason}, "
                        f"submitted={has_submitted}, api_turns={api_turn_count}, "
                        f"sdk_turns={message.num_turns}, in_tokens={in_tokens}, out_tokens={out_tokens}"
                    )
                    break

        return {
            "result": result_text,
            "has_submitted": has_submitted,
            "api_turns": api_turn_count,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
        }
