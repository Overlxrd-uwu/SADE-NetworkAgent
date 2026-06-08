"""Parse messages.jsonl to extract agent trace metrics.

The parser reads the unified ``messages.jsonl`` file and optionally filters
by the ``agent`` field.  Token counts, step counts, and timing are derived
from the diagnosis agent by default (``agent_filter="diagnosis_agent"``).
"""

import json
from datetime import datetime


class AgentTraceParser:
    def __init__(self, trace_path: str, agent_filter: str | None = "diagnosis_agent") -> None:
        self.trace_path = trace_path
        self.agent_filter = agent_filter
        self.in_tokens = 0
        self.out_tokens = 0
        self.steps = 0
        self.tool_calls = 0
        self.tool_errors = 0
        self.time_taken = 0

    def parse_trace(self) -> dict:
        time_start: datetime | None = None
        time_end: datetime | None = None

        with open(self.trace_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if self.agent_filter and entry.get("agent") != self.agent_filter:
                    continue

                raw_ts = entry.get("timestamp")
                if raw_ts:
                    cur_time = datetime.fromisoformat(raw_ts)
                    if time_start is None or cur_time < time_start:
                        time_start = cur_time
                    if time_end is None or cur_time > time_end:
                        time_end = cur_time

                event = entry.get("event")
                if event == "tool_start":
                    self.tool_calls += 1
                elif event == "tool_error":
                    self.tool_errors += 1
                elif event == "llm_end":
                    self.steps += 1
                    usage_metadata = entry.get("usage_metadata") or {}
                    self.in_tokens += usage_metadata.get("input_tokens", 0)
                    self.out_tokens += usage_metadata.get("output_tokens", 0)

        self.time_taken = (time_end - time_start).total_seconds() if time_start and time_end else 0
        return {
            "in_tokens": self.in_tokens,
            "out_tokens": self.out_tokens,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "time_taken": self.time_taken,
        }
