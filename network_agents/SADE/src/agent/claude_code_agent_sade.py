"""
ClaudeCodeAgentSADE: SADE-enhanced diagnosis agent.

Uses the Symptom-Aware Diagnosis Escalation (SADE) prompt to enforce
an explicit workflow:
- blind start
- symptom-first diagnosis
- broad lower-to-higher-layer escalation only when no symptom exists
- no-anomaly submission only after all checked layers stay clean

Uses ClaudeSDKClient for bidirectional messaging, enabling turn-aware
reminders that reinforce the workflow before the agent runs out of turns.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

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

from agent.prompts.sade_prompt import SADE_PROMPT
from agent.utils.mcp_servers import MCPServerConfig
from nika.config import BASE_DIR
from nika.utils.logger import system_logger

load_dotenv()


def _require_api_key() -> str:
    """Return the ANTHROPIC_API_KEY loaded from .env / environment.

    The SADE agent runs in API-key mode: the key is read from `.env` (loaded
    via `load_dotenv()` above) and passed explicitly to the spawned Claude
    Code CLI via `ClaudeAgentOptions.env`, which the SDK merges on top of
    `os.environ` when starting the subprocess. Failing loud here is better
    than letting the subprocess silently fall through to OAuth/keychain
    credentials that may bill an unrelated account."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to "
            f"{Path(BASE_DIR) / '.env'} or export it in the shell before running."
        )
    return api_key


logger = logging.getLogger(__name__)

# Turn counting: we count ThinkingBlocks as a proxy for "decision moments" —
# one per assistant turn that includes reasoning. This undercounts the SDK's
# own `num_turns` (which also counts pure tool-use turns and internal
# orchestration), but the undercount is a known trade-off. The earlier
# attempt to align with SDK turn count via `include_partial_messages=True`
# was reverted: that flag silently enables CLAUDE_CODE_ENABLE_FINE_GRAINED_
# TOOL_STREAMING in the subprocess, which changed how tool-heavy turns
# interact with the API and caused intermittent prompt-too-long failures
# on l-size topologies. Counter accuracy is worth less than session stability.
TURN_REMINDER_FRAC = 0.50


class ClaudeCodeAgentSADE:
    """
    SADE-enhanced network diagnosis agent.

    Identical to ClaudeCodeAgent except for the system prompt and the
    turn reminder, which now explicitly reinforce the SADE workflow.
    """

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        diagnosis_config = MCPServerConfig().load_config(if_submit=False)
        submission_config = MCPServerConfig().load_config(if_submit=True)
        self.mcp_servers = {**diagnosis_config, **submission_config}

    def _setup_conv_logger(self) -> logging.Logger:
        """Set up a file logger writing JSONL to conversation_diagnosis_agent.log."""
        conv_logger = logging.getLogger("ClaudeCodeSADEConvLogger")
        conv_logger.setLevel(logging.INFO)
        conv_logger.propagate = False
        for handler in list(conv_logger.handlers):
            conv_logger.removeHandler(handler)

        with open(f"{BASE_DIR}/runtime/current_session.json", "r") as f:
            session_info = json.load(f)

        log_path = os.path.join(
            session_info["session_dir"],
            "conversation_diagnosis_agent.log",
        )
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        conv_logger.addHandler(file_handler)
        return conv_logger

    def _log_event(self, conv_logger: logging.Logger, event_type: str, payload: dict):
        entry = {"timestamp": str(datetime.now()), "event": event_type, **payload}
        conv_logger.info(json.dumps(entry, ensure_ascii=False, default=str))

    async def run(self, task_description: str) -> str:
        """
        Run the SADE-enhanced Claude Code agent on a diagnosis task.

        Uses ClaudeSDKClient for bidirectional messaging. Tracks turn count
        and injects a single gentle reminder at the halfway mark
        (TURN_REMINDER_FRAC of max_turns, default 50%) to reinforce the
        SADE workflow without panic language. Halfway leaves enough budget
        for the agent to act on the reminder before the cap.

        Returns the final result string from the agent.
        """
        system_logger.info("ClaudeCodeAgentSADE: starting session")

        conv_logger = self._setup_conv_logger()
        result_text = ""
        api_turn_count = 0
        tool_result_count = 0
        reminded = False
        has_submitted = False
        turn_reminder = int(self.max_turns * TURN_REMINDER_FRAC)

        api_key = _require_api_key()
        system_logger.info(
            f"ClaudeCodeAgentSADE: auth mode = api_key (key ends ...{api_key[-4:]})"
        )
        options = ClaudeAgentOptions(
            system_prompt=SADE_PROMPT,
            model="claude-sonnet-4-6",
            cwd=str(Path(__file__).resolve().parent),
            mcp_servers=self.mcp_servers,
            max_turns=self.max_turns,
            permission_mode="bypassPermissions",
            setting_sources=["project"],
            env={
                "ANTHROPIC_API_KEY": api_key,
                "ANTHROPIC_AUTH_TOKEN": "",
            },
        )

        self._log_event(
            conv_logger,
            "session_config",
            {
                "system_prompt": SADE_PROMPT,
                "user_prompt": task_description,
                "max_turns": self.max_turns,
                "mcp_servers": list(self.mcp_servers.keys()),
                "workflow": "SADE",
            },
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(task_description)

            async for message in client.receive_messages():
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    session_id = message.data.get("session_id")
                    system_logger.info(
                        f"ClaudeCodeAgentSADE: session started - {session_id}"
                    )

                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            api_turn_count += 1
                            self._log_event(
                                conv_logger,
                                "thinking",
                                {
                                    "text": block.thinking,
                                    "api_turn": api_turn_count,
                                },
                            )
                        elif isinstance(block, TextBlock):
                            self._log_event(
                                conv_logger,
                                "assistant_text",
                                {"text": block.text},
                            )
                        elif isinstance(block, ToolUseBlock):
                            self._log_event(
                                conv_logger,
                                "tool_start",
                                {
                                    "tool": {"name": block.name},
                                    "input": str(block.input),
                                },
                            )
                            if "submit" in block.name:
                                has_submitted = True

                elif isinstance(message, UserMessage):
                    content = message.content if isinstance(message.content, list) else []
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            tool_result_count += 1
                            self._log_event(
                                conv_logger,
                                "tool_end",
                                {
                                    "output": str(block.content),
                                    "is_error": block.is_error,
                                },
                            )

                    remaining = self.max_turns - api_turn_count
                    if not has_submitted and api_turn_count >= turn_reminder and not reminded:
                        reminded = True
                        reminder = (
                            f"SADE REMINDER: API turn {api_turn_count}/{self.max_turns} "
                            f"({remaining} remaining). "
                            "If direct evidence on the owning device already matches a fault-family fingerprint, submit NOW — do not hypothesize secondary mechanisms the topology does not support. "
                            "If you have a symptom but no owner yet, stay on that lead and stop broad probing. "
                            "If you still have no symptom, do one broad lower-to-higher-layer escalation sweep, then submit `is_anomaly=False` only if that sweep finds nothing. "
                            "Check the submit() signature in CLAUDE.md before calling — wrong types end the session."
                        )
                        self._log_event(
                            conv_logger,
                            "turn_reminder",
                            {
                                "api_turn": api_turn_count,
                                "remaining": remaining,
                                "text": reminder,
                            },
                        )
                        await client.query(reminder)
                        system_logger.info(
                            f"ClaudeCodeAgentSADE: REMINDER at API turn {api_turn_count}/{self.max_turns}"
                        )

                elif isinstance(message, ResultMessage):
                    result_text = message.result
                    # Pull token counts out of the usage dict into top-level
                    # fields so they're easy to grep from logs regardless of
                    # how the session ended (successful submit, cap hit with
                    # no submit, API error, etc).
                    usage = message.usage or {}
                    token_summary = {
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cache_creation_input_tokens": usage.get(
                            "cache_creation_input_tokens", 0
                        ),
                        "cache_read_input_tokens": usage.get(
                            "cache_read_input_tokens", 0
                        ),
                    }
                    token_summary["total_input_tokens"] = (
                        token_summary["input_tokens"]
                        + token_summary["cache_creation_input_tokens"]
                        + token_summary["cache_read_input_tokens"]
                    )
                    self._log_event(
                        conv_logger,
                        "llm_end",
                        {
                            "result": result_text,
                            "stop_reason": message.stop_reason,
                            "num_turns": message.num_turns,
                            "has_submitted": has_submitted,
                            "tokens": token_summary,
                            "usage": message.usage,
                        },
                    )
                    system_logger.info(
                        "ClaudeCodeAgentSADE: session complete - "
                        f"stop_reason={message.stop_reason}, "
                        f"submitted={has_submitted}, "
                        f"api_turns={api_turn_count}, "
                        f"sdk_turns={message.num_turns}, "
                        f"tool_results={tool_result_count} | "
                        f"tokens: input={token_summary['input_tokens']}, "
                        f"cache_create={token_summary['cache_creation_input_tokens']}, "
                        f"cache_read={token_summary['cache_read_input_tokens']}, "
                        f"output={token_summary['output_tokens']}, "
                        f"total_input={token_summary['total_input_tokens']}"
                    )
                    break

        return result_text
