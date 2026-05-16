import json
from datetime import datetime


class AgentTraceParser:
    def __init__(self, trace_path: str):
        self.trace_path = trace_path
        self.in_tokens = 0
        self.out_tokens = 0
        self.steps = 0
        self.tool_calls = 0
        self.tool_errors = 0
        self.time_taken = 0

    def parse_trace(self):
        time_start = None
        time_end = None
        with open(self.trace_path, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                cur_time = entry.get("timestamp")
                cur_time = datetime.strptime(cur_time, "%Y-%m-%d %H:%M:%S.%f")
                if time_start is None or cur_time < time_start:
                    time_start = cur_time
                if time_end is None or cur_time > time_end:
                    time_end = cur_time

                if entry.get("event") == "tool_start":
                    self.tool_calls += 1
                # TODO: there are some validation errors from MCP, also handle this
                elif entry.get("event") == "tool_error":
                    self.tool_errors += 1
                elif entry.get("event") == "llm_end":
                    self.steps += 1
                    self._accumulate_tokens(entry)

        self.time_taken = (time_end - time_start).total_seconds() if time_start and time_end else 0
        return {
            "in_tokens": self.in_tokens,
            "out_tokens": self.out_tokens,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "time_taken": self.time_taken,
        }

    def _accumulate_tokens(self, entry: dict) -> None:
        """Pull token counts out of one llm_end entry, regardless of pipeline.

        Three formats are handled:
          1. LangGraph (ReAct runner) - ``usage_metadata.{input,output}_tokens``,
             one llm_end per turn, summed.
          2. Claude Code SDK (CC-Baseline / SADE runners) -
             ``tokens.{total_input_tokens,output_tokens}``,
             one terminal llm_end per session whose ``total_input_tokens``
             already aggregates raw + cache_creation + cache_read.
          3. Raw Anthropic ``usage`` block as a fallback - same fields as
             above but without the precomputed ``total_input_tokens``.

        Without this dispatch the Claude pipeline logged ``in_tokens=0`` /
        ``out_tokens=0`` because the parser only knew the LangGraph schema,
        and ``scripts/augment_token_counts.py`` had to patch the CSV after
        the fact.
        """
        # 1. LangGraph
        usage_metadata = entry.get("usage_metadata") or {}
        if usage_metadata.get("input_tokens") or usage_metadata.get("output_tokens"):
            self.in_tokens += int(usage_metadata.get("input_tokens", 0) or 0)
            self.out_tokens += int(usage_metadata.get("output_tokens", 0) or 0)
            return

        # 2. Claude Code SDK (precomputed total)
        tokens = entry.get("tokens") or {}
        if tokens:
            total_in = tokens.get("total_input_tokens")
            if total_in is None:
                total_in = (
                    int(tokens.get("input_tokens", 0) or 0)
                    + int(tokens.get("cache_creation_input_tokens", 0) or 0)
                    + int(tokens.get("cache_read_input_tokens", 0) or 0)
                )
            self.in_tokens += int(total_in or 0)
            self.out_tokens += int(tokens.get("output_tokens", 0) or 0)
            return

        # 3. Raw Anthropic usage fallback
        usage = entry.get("usage") or {}
        if usage:
            self.in_tokens += (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("cache_creation_input_tokens", 0) or 0)
                + int(usage.get("cache_read_input_tokens", 0) or 0)
            )
            self.out_tokens += int(usage.get("output_tokens", 0) or 0)
