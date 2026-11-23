# Changelog

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
