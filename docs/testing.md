# Testing

## 1. Hook tests (automated)

From the repository root:

```
python tests/test_hooks.py
```

29 tests build throwaway project folders and feed the hooks the same JSON Claude Code sends.
They cover: plugin invisible when not set up, normal use unaffected without a ticket, Gate A,
approved-developer-only edits (namespaced and bare names), STOP/RESUME/CANCEL, protected control
files, edits outside the project, blocked and allowed shell commands, and secret files. If `sh`
is on PATH (Git Bash on Windows), the Gate A scenarios also run through `run-hook.sh`, exactly as
`hooks/hooks.json` calls them.

### MCP server tests

```
python tests/test_mcp.py
```

9 tests write fake transcripts into a temporary `CLAUDE_CONFIG_DIR`, start the server as a child
process and exchange JSON-RPC messages with it: handshake, `tools/list`, usage totals (each reply
counted once, subagents named by type), bad arguments returned as tool errors, unknown methods.

## 2. Plugin install check

1. `/plugin marketplace add <path to this repo>` then `/plugin install devorg@devorg-marketplace`.
2. `/agents` lists the six `devorg:` agents. `/hooks` shows the DevOrg hooks.
3. In a project **without** `/devorg:init`: edit a file and type `APPROVE PLAN`. Nothing should
   happen (no block, no gate message).
4. `/mcp` lists `plugin:devorg:token-tracker` as connected. Ask "how many tokens has this session
   used, by agent?"; Claude should call `session_usage` and show a table.

**Confirm on the first install** (not covered by the docs, so the code accepts both forms):
- the name the Manager must pass to the Agent tool (`devorg:ticket-reviewer` vs `ticket-reviewer`);
- the `agent_type` a plugin subagent reports to hooks (the guard strips any `devorg:` prefix).

## 3. End-to-end checklist (one small ticket in a real or throwaway project)

| # | Check | Pass when |
|---|---|---|
| 1 | `/devorg:init` | config.json + rules.md created, `.devorg/` in `.gitignore`, test command sensible |
| 2 | `/devorg:run "<small ticket>"` | git check runs; ticket folder + state.json created |
| 3 | Analysis | requirements map to testable acceptance criteria; open questions have defaults; a complexity LEVEL and a Context brief are present |
| 3b | Track | a typo fix runs as trivial (no design, 1 developer, 1 verifier); a ticket touching validation is at least standard; `--track complex` is respected |
| 3c | Context brief used | architect/developer outputs list few or no "files read beyond the brief" |
| 4 | Design | triangle fits the ticket; each weight has a reason |
| 5 | Proposals | three genuinely different proposals; each states what it gave up; `log.md` shows each got only shared files + its corner |
| 6 | Decision | baseline gate done; score table adds up; reasons convincing |
| 7 | Gate A | workflow waits; typing anything but a keyword doesn't proceed; asking Claude to "just edit the file" is blocked by the guard |
| 8 | `REJECT PLAN weights: …` | comparison re-runs with the new weights |
| 9 | Implementation | only the approved developer's edits succeed |
| 10 | Rework | a failing check goes back to the developer with no reviewer call; a failing review returns to step 7 and only the failed review re-runs |
| 10b | Models | `session_usage` lists the sonnet and opus models per the agent files |
| 11 | Gate B | waits for `APPROVE FINAL`; `final-report.md` lists approvals with timestamps |
| 12 | Finish | phase `done`; guards off; commit offered, never pushed |

Tip: to provoke the rework loop, add a requirement the first attempt is likely to miss
(e.g. "results must be sorted oldest first").

## Mapping to the original acceptance criteria

| Original AC | Covered by |
|---|---|
| AC1 setup | install check (agents listed) |
| AC2 analysis + design | checklist 3–4 |
| AC3 distinct proposals + reasons | checklist 5–6 |
| AC4 Gate A, no code before approval | checklist 7–8, hook tests `BeforeGateA` |
| AC5 only the selected developer, no secrets/push | checklist 9, hook tests `AfterGateA`, `CommandGuard` |
| AC6 reviewers report without editing | reviewer tool lists; checklist 10 |
| AC7 rework loop + limit | checklist 10, `max_revisions` |
| AC8 criteria with evidence | acceptance review table |
| AC9 Gate B, pause/stop | checklist 11, hook tests `test_stop_and_resume` |
| AC10 records | `.devorg/tickets/<ID>/`, `final-report.md` |
