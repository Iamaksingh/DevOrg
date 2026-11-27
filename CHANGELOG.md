# Changelog

## 0.4.0 — security review

- **Security Reviewer** (`agents/security-reviewer.md`, opus, read-only): reviews the change for
  exploitable issues with a 10-category checklist. Severities: critical / high → rework;
  medium / low → reported at Gate B with suggested follow-ups.
- **The human decides at Gate A:** the Manager recommends on or off with reasons; reply
  `APPROVE PLAN security: on|off` (if missing, the Manager asks).
- **Free pre-scan after coding:** the Manager searches the diff for risky patterns. Risky code with
  security off → asks the human (drift). No risky code with security on → says it's not
  recommended; the human decides.
- **Order:** security runs before the Senior Developer; on complex tickets in parallel with the
  Architect and Ticket Reviewer.
- **Fewer tokens:** at most 2 security reworks, then the workflow continues and unresolved
  findings are flagged at Gate B. Re-checks (`MODE RECHECK`) look only at what the rework changed
  and run on sonnet. Compact output.
- Senior Developer: also flags hard-coded values; security moved to the Security Reviewer (a low
  note for obvious problems when security is off).
- Hook tests: the Security Reviewer is blocked from editing.

## 0.3.0 — fewer tokens per ticket

- **Complexity tracks.** The Ticket Reviewer rates each ticket trivial / standard / complex.
  Trivial: one developer (Simplicity), no design, one verifier. Standard: design without triangle,
  one developer, one verifier. Complex: the full team. Sensitive areas (auth, validation,
  secrets, schema, payments, public APIs) force at least standard; the Manager may only raise the
  track; the human can set it with `--track` or `REJECT PLAN track: <level>`. Gates and hooks
  apply on every track.
- **Context brief.** The analysis ends with relevant files, key code, conventions and commands.
  Architect and developers start from it and justify any extra file they read; reviewers still
  read freely.
- **Model per role.** `model:` in each agent: opus for System Architect and Senior Developer,
  sonnet for Ticket Reviewer and developers.
- **Checks before reviews.** New optional `check_commands` (build, lint) run before
  `test_command`; failing checks go straight back to the developer with no reviewer call.
- **One verifier on short tracks.** Senior Developer `MODE VERIFY` combines code review and
  acceptance check. On complex tickets the three reviews run in parallel and all findings go
  back in one rework round; only failed reviews re-run.
- `/devorg:init` no longer records a test command that can't pass; suggests check commands.
- Phases renamed: `testing` → `checks`; the three review phases → `verification`. Revision
  counters: `checks`, `verify`, `architecture`, `code`, `acceptance`.
- Hook tests: 29 (new: short-track Gate A).

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
