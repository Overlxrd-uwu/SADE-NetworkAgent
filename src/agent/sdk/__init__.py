"""Claude / Codex SDK agents (planned).

Direct integration with vendor SDKs, bypassing LangChain chat models:
- Anthropic SDK for Claude
- Cursor SDK (``cursor-sdk`` / ``@cursor/sdk``) for Codex

Expected layout::

    sdk/
      agent.py          # SdkAgent entry point
      claude_agent.py   # optional split by vendor
      codex_agent.py

Both phases (diagnosis → submission) should still write to
``{session_dir}/messages.jsonl`` via ``AgentCallbackLogger`` or an SDK-specific
adapter with the same event schema.
"""

__all__: list[str] = []
