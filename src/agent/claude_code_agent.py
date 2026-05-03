"""
ClaudeCodeAgent: inner diagnosis agent powered by the Claude Agent SDK.

Spawns a Claude Code CLI subprocess that connects to NIKA's MCP servers and
diagnoses the network, then calls submit() with its findings.

Requires ANTHROPIC_API_KEY (Claude API quota is consumed by the inner agent).
Use agent_type='react' with a non-Claude backend_model to avoid Claude rate limits.

Flow:
  NIKA step3 -> ClaudeCodeAgent.run()
    -> claude_agent_sdk.query() spawns Claude Code CLI subprocess
      -> inner Claude connects to NIKA MCP servers (kathara, frr, telemetry, task)
        -> diagnoses network and calls submit() with findings
          -> ResultMessage returned to NIKA
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    UserMessage,
    ToolResultBlock,
    query,
)
from dotenv import load_dotenv

from agent.prompts.baseline_prompt import BASELINE_PROMPT
from agent.utils.mcp_servers import MCPServerConfig
from nika.config import BASE_DIR
from nika.utils.logger import system_logger

load_dotenv()


def _resolve_anthropic_auth() -> str:
    """Return the auth mode the spawned Claude Code CLI will use.

    If ANTHROPIC_API_KEY is set we authenticate via API key (billed to that
    key). Otherwise we fall back to the OAuth/keychain credentials saved by
    a prior `claude /login` (billed against the user's Pro/Max plan). At
    least one must be present or the SDK subprocess will fail to start."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return "api_key"
    return "oauth"


logger = logging.getLogger(__name__)

CLAUDE_CODE_SUBMIT_RULE = """\
Claude Code benchmark hard rule:
- The final benchmark answer must be submitted with the exact tool `mcp__task_mcp_server__submit`.
- Do not end the session with only a written diagnostic report. If `submission.json` is not created, the run fails.
- As soon as you have enough evidence for is_anomaly, faulty_devices, and root_cause_name, call `mcp__task_mcp_server__submit`.
- If the submit tool is not visible, first use ToolSearch with `select:mcp__task_mcp_server__list_avail_problems,mcp__task_mcp_server__submit`.
- After `mcp__task_mcp_server__submit` returns success, stop.
""".strip()

SYSTEM_PROMPT = f"{BASELINE_PROMPT}\n\n{CLAUDE_CODE_SUBMIT_RULE}"


class ClaudeCodeAgent:
    """
    Agentic network troubleshooter powered by the Claude Code CLI via Agent SDK.

    Replaces the LangGraph-based BasicReActAgent. Uses all of NIKA's existing
    MCP servers without modification — the Agent SDK mcp_servers dict format
    matches NIKA's MCPServerConfig output exactly.
    """

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        # Load all MCP servers: diagnosis tools + submission tool in one session
        diagnosis_config = MCPServerConfig().load_config(if_submit=False)
        submission_config = MCPServerConfig().load_config(if_submit=True)
        self.mcp_servers = {**diagnosis_config, **submission_config}

    def _setup_conv_logger(self) -> logging.Logger:
        """Set up a file logger writing JSONL to conversation_diagnosis_agent.log."""
        conv_logger = logging.getLogger("ClaudeCodeConvLogger")
        conv_logger.setLevel(logging.INFO)
        conv_logger.propagate = False
        for h in list(conv_logger.handlers):
            conv_logger.removeHandler(h)

        with open(f"{BASE_DIR}/runtime/current_session.json", "r") as f:
            session_info = json.load(f)

        log_path = os.path.join(
            session_info["session_dir"],
            "conversation_diagnosis_agent.log",
        )
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8", mode="a")
        fh.setFormatter(logging.Formatter("%(message)s"))
        conv_logger.addHandler(fh)
        return conv_logger

    def _log_event(self, conv_logger: logging.Logger, event_type: str, payload: dict):
        entry = {"timestamp": str(datetime.now()), "event": event_type, **payload}
        conv_logger.info(json.dumps(entry, ensure_ascii=False, default=str))

    async def run(self, task_description: str) -> str:
        """
        Run the Claude Code agent on a diagnosis task.

        Returns the final result string from the agent.
        """
        system_logger.info("ClaudeCodeAgent: starting session")

        conv_logger = self._setup_conv_logger()
        result_text = ""
        session_id = None

        # Log the initial prompt and system prompt so we can see LLM input
        self._log_event(conv_logger, "session_config", {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": task_description,
            "max_turns": self.max_turns,
            "mcp_servers": list(self.mcp_servers.keys()),
        })

        auth_mode = _resolve_anthropic_auth()
        system_logger.info(f"ClaudeCodeAgent: auth mode = {auth_mode}")
        async for message in query(
            prompt=task_description,
            options=ClaudeAgentOptions(
                system_prompt=SYSTEM_PROMPT,
                model="claude-sonnet-4-6",
                mcp_servers=self.mcp_servers,
                max_turns=self.max_turns,
                permission_mode="bypassPermissions",
            ),
        ):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                session_id = message.data.get("session_id")
                system_logger.info(f"ClaudeCodeAgent: session started — {session_id}")

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ThinkingBlock):
                        self._log_event(conv_logger, "thinking", {
                            "text": block.thinking,
                        })
                    elif isinstance(block, TextBlock):
                        self._log_event(conv_logger, "assistant_text", {
                            "text": block.text,
                        })
                    elif isinstance(block, ToolUseBlock):
                        self._log_event(conv_logger, "tool_start", {
                            "tool": {"name": block.name},
                            "input": str(block.input),
                        })

            elif isinstance(message, UserMessage):
                content = message.content if isinstance(message.content, list) else []
                for block in content:
                    if isinstance(block, ToolResultBlock):
                        self._log_event(conv_logger, "tool_end", {
                            "output": str(block.content),
                            "is_error": block.is_error,
                        })

            elif isinstance(message, ResultMessage):
                result_text = message.result
                self._log_event(conv_logger, "llm_end", {
                    "result": result_text,
                    "stop_reason": message.stop_reason,
                    "num_turns": message.num_turns,
                    "usage": message.usage,
                })
                system_logger.info(
                    f"ClaudeCodeAgent: session complete — stop_reason={message.stop_reason}"
                )

        return result_text
