"""Inspect the agent's reasoning trace before submit on a P4 case."""
import json
import sys

log = sys.argv[1] if len(sys.argv) > 1 else "results/p4_table_entry_misconfig/0501132339/conversation_diagnosis_agent.log"
with open(log, encoding="utf-8") as f:
    events = [json.loads(l) for l in f if l.strip()]

# Find submit
submit_idx = None
for i, e in enumerate(events):
    if e.get("event") == "tool_start" and "submit" in e.get("tool", {}).get("name", ""):
        submit_idx = i
        break

# The 5 events just before submit, plus the submit input
window = events[max(0, submit_idx - 6):submit_idx + 1] if submit_idx is not None else events[-6:]
for e in window:
    et = e.get("event", "?")
    if et == "thinking":
        text = e.get("text", "")
        # Trim and ASCII-fold to avoid console encoding errors
        text = text.encode("ascii", errors="replace").decode("ascii")
        print(f"--- THINKING (api_turn {e.get('api_turn')}) ---")
        print(text[:2500])
    elif et == "assistant_text":
        text = e.get("text", "").encode("ascii", errors="replace").decode("ascii")
        print(f"--- ASSISTANT TEXT ---")
        print(text[:2500])
    elif et == "tool_start":
        tool = e.get("tool", {}).get("name", "?")
        inp = str(e.get("input", "")).encode("ascii", errors="replace").decode("ascii")
        print(f"--- TOOL_START: {tool} ---")
        print(inp[:600])
    elif et == "tool_end":
        out = str(e.get("output", "")).encode("ascii", errors="replace").decode("ascii")
        print(f"--- TOOL_END (is_error={e.get('is_error')}) ---")
        print(out[:800])
    print()
