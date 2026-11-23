# Changelog

## 0.2.0

- New `token-tracker` MCP server (`plugins/devorg/mcp/token_tracker.py`, registered in
  `.mcp.json`): read-only tools `list_sessions`, `session_usage` and `usage_by_agent` report token
  usage from Claude Code's transcripts, split by main session, subagent type and model. Standard
  library only; the JSON-RPC protocol is implemented by hand for learning purposes.
- The Manager shows token usage at Gate A and Gate B and in `final-report.md`; `/devorg:status`
  shows the session total.
- `tests/test_mcp.py`: 9 tests that drive the server over stdin/stdout like Claude Code does.

## 0.1.0

First generic plugin release.

- Packaged as a Claude Code plugin (`devorg`) with a local marketplace.
- Six subagents (ticket reviewer, system architect, developers 1–3, senior developer); the
  Engineering Manager runs as the main session via `/devorg:run`.
- Skills: `/devorg:init`, `/devorg:run`, `/devorg:status`.
- Trade-off triangle: per-ticket corners and weights, developer baseline, weighted scoring,
  SELECT or HYBRID decisions with an architect coherence check.
- Hooks: human approval gates (APPROVE/REJECT PLAN/FINAL, STOP, RESUME, CANCEL), edit guard
  (Gate A, approved developer only, protected control files), command guard (no push/merge/
  deploy/network/destructive commands), secrets guard. Inactive outside DevOrg projects and
  outside running tickets.
- Project settings in `.devorg/config.json`; organisation rules in `.devorg/rules.md`;
  `.devorg/` git-ignored.
- Removed the todo-app demo, the PDF and project-specific settings; original proposal kept in
  `docs/history/`.
