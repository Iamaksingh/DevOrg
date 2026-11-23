# DevOrg

**An AI software team for any project, as a Claude Code plugin.**

Instead of one assistant that plans, writes and checks its own work, DevOrg splits a ticket across
specialist agents — a manager, a ticket reviewer, an architect, three developers and a senior
reviewer — and keeps a human in charge with two approval gates that are **enforced by hooks**,
not just requested in prompts.

```
ticket → analysis → design + trade-off triangle → 3 parallel proposals → weighted decision
       → GATE A (you approve the plan) → implement → tests → 3 reviews (with rework loop)
       → GATE B (you approve the result) → done
```

## Install

In Claude Code (terminal or VS Code), point it at this repository — a local path or a git URL:

```
/plugin marketplace add <path-or-git-url-of-this-repo>
/plugin install devorg@devorg-marketplace
```

Then, in each project where you want the team:

```
/devorg:init                       # once per project: test command, rules, .gitignore
/devorg:run tickets/PROJ-12.md     # or: /devorg:run "Add CSV export to the reports page"
```

Requirements: git, and Python 3.8+ on PATH (the guard hooks are a small standard-library script).
On Windows, Claude Code runs hooks through Git Bash.

## Using it

| You type | What happens |
|---|---|
| `/devorg:init` | Sets the project up (`.devorg/config.json`, `.devorg/rules.md`, `.gitignore`) |
| `/devorg:run <ticket>` | Starts the workflow; the session becomes the Engineering Manager |
| `APPROVE PLAN [notes]` / `REJECT PLAN <reason>` | Gate A — must be typed, uppercase, at the start of the message |
| `APPROVE FINAL` / `REJECT FINAL <reason>` | Gate B |
| `STOP` / `RESUME` / `CANCEL` | Freeze all edits / continue / close the ticket |
| `/devorg:status` | Where the ticket stands and what's expected next |
| `/devorg:run resume` | Continue in a new session |

DevOrg is invisible in projects without `.devorg/config.json`, and its guards are only active
while a ticket is running, so normal Claude Code use is unaffected.

## Repository layout

```
.claude-plugin/marketplace.json   makes this repo installable with /plugin
plugins/devorg/                   the plugin itself
  .claude-plugin/plugin.json        plugin manifest (name, version)
  agents/                           6 subagents: ticket-reviewer, system-architect,
                                    developer-1/2/3, senior-developer
  skills/run/                       /devorg:run    — the Engineering Manager's playbook
  skills/init/                      /devorg:init   — project setup + org-rules.md template
  skills/status/                    /devorg:status — read-only status report
  hooks/hooks.json                  when the guards run
  scripts/                          what the guards do (devorg_hooks.py + run-hook.sh launcher)
tests/test_hooks.py               28 tests for the guards
docs/                             how it works, safety, configuration, testing
docs/history/                     the original proposal
```

## Documentation

- [Architecture](docs/architecture.md) — agents vs subagents, roles, context isolation
- [Workflow](docs/workflow.md) — the 12 steps, the trade-off triangle, gates, rework, records
- [Safety](docs/safety.md) — what is enforced by code, what by instructions, known gaps
- [Configuration](docs/configuration.md) — `config.json`, `rules.md`, permissions
- [Testing](docs/testing.md) — running the hook tests, the end-to-end checklist
- [Changelog](CHANGELOG.md)
