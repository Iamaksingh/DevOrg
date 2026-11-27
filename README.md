# DevOrg

**An AI software team for any project, as a Claude Code plugin.**

Instead of one assistant that plans, writes and checks its own work, DevOrg splits a ticket across
specialist agents — a manager, a ticket reviewer, an architect, three developers, a senior
reviewer and an optional security reviewer — and keeps a human in charge with two approval gates that are **enforced by hooks**,
not just requested in prompts.

```
ticket → analysis + complexity rating + context brief
  trivial:  1 developer (simplicity)                        ┐
  standard: design → 1 developer                            ├→ GATE A (you approve the plan
                                                            │          and choose security on/off)
  complex:  design + trade-off triangle → 3 parallel        │
            proposals → weighted decision                   ┘
       → implement → build/lint/tests → security review (if on) → verification
         (1 verifier, or 3 parallel reviews on complex)
       → GATE B (you approve the result) → done
```

Small tickets get a small team: only complex tickets pay for the full competition.

## Setup

### 1. Prerequisites

| You need | Check with | Notes |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) (terminal or VS Code extension) | `claude --version` | |
| git | `git --version` | **Windows:** install [Git for Windows](https://git-scm.com/download/win) — Claude Code runs the DevOrg hooks through its Git Bash |
| Python 3.8+ on PATH | Windows: `python --version` · macOS/Linux: `python3 --version` | the hooks and the token tracker are small standard-library scripts; nothing to `pip install` |

### 2. Install the plugin

Inside Claude Code, type:

```
/plugin marketplace add Iamaksingh/DevOrg
/plugin install devorg@devorg-marketplace
```

Then restart Claude Code (in VS Code: *Developer: Reload Window*).

**If you see "`/plugin` isn't available in this environment"** (this happens in some VS Code
versions), run the same steps from a normal terminal with the `claude` command line:

```
claude plugin marketplace add Iamaksingh/DevOrg
claude plugin install devorg@devorg-marketplace
```

If `claude` isn't found, use the copy bundled with the VS Code extension:

- **Windows (PowerShell)**
  ```powershell
  $claude = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" | Select-Object -Last 1).FullName
  & $claude plugin marketplace add Iamaksingh/DevOrg
  & $claude plugin install devorg@devorg-marketplace
  ```
  `$claude` only lasts for that terminal window; set it again in a new one.
- **macOS / Linux**
  ```bash
  claude=$(ls -d ~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude | tail -1)
  "$claude" plugin marketplace add Iamaksingh/DevOrg
  "$claude" plugin install devorg@devorg-marketplace
  ```

Then reload the VS Code window.

### 3. Check that it worked

| Type | You should see |
|---|---|
| `/agents` | 7 `devorg:` agents (ticket-reviewer, system-architect, developer-1/2/3, senior-developer, security-reviewer) |
| `/hooks` | the DevOrg hooks |
| `/mcp` | `plugin:devorg:token-tracker` connected |

### 4. Use it in a project

Open the project in Claude Code, then:

```
/devorg:init                       # once per project: test/check commands, rules, .gitignore
/devorg:run "Add CSV export to the reports page"     # or: /devorg:run tickets/PROJ-12.md
```

`/devorg:init` asks you to confirm the test and build commands it finds. DevOrg stays inactive in
projects where you haven't run it.

### 5. Update to a new version

```
/plugin marketplace update devorg-marketplace
/plugin update devorg@devorg-marketplace
```

(or `claude plugin marketplace update devorg-marketplace` and
`claude plugin update devorg@devorg-marketplace` from a terminal), then restart Claude Code.

Each project keeps its own copy of the rules in `.devorg/rules.md`. After an update, run
`/devorg:init --force` in each project to get the new rules (it asks before replacing a copy you
edited).

### 6. Uninstall

```
/plugin uninstall devorg@devorg-marketplace
/plugin marketplace remove devorg-marketplace
```

(or the same with `claude plugin …` from a terminal). To remove DevOrg from a project, delete its
`.devorg/` folder and the `.devorg/` line in `.gitignore`.

## Using it

| You type | What happens |
|---|---|
| `/devorg:init` | Sets the project up (`.devorg/config.json`, `.devorg/rules.md`, `.gitignore`) |
| `/devorg:run <ticket>` | Starts the workflow; the session becomes the Engineering Manager |
| `/devorg:run <ticket> --track complex` | Same, but you choose the track instead of the Ticket Reviewer |
| `APPROVE PLAN security: on\|off [notes]` / `REJECT PLAN <reason>` | Gate A — must be typed, uppercase, at the start of the message. The Manager recommends whether the security review is needed; you decide |
| `APPROVE FINAL` / `REJECT FINAL <reason>` | Gate B |
| `STOP` / `RESUME` / `CANCEL` | Freeze all edits / continue / close the ticket |
| `/devorg:status` | Where the ticket stands and what's expected next |
| `/devorg:run resume` | Continue in a new session |
| "How many tokens did this session use, by agent?" | Claude calls the `token-tracker` MCP server (works in any project) |

DevOrg is invisible in projects without `.devorg/config.json`, and its guards are only active
while a ticket is running, so normal Claude Code use is unaffected.

## Repository layout

```
.claude-plugin/marketplace.json   makes this repo installable with /plugin
plugins/devorg/                   the plugin itself
  .claude-plugin/plugin.json        plugin manifest (name, version)
  agents/                           7 subagents: ticket-reviewer, system-architect,
                                    developer-1/2/3, senior-developer, security-reviewer
  skills/run/                       /devorg:run    — the Engineering Manager's playbook
  skills/init/                      /devorg:init   — project setup + org-rules.md template
  skills/status/                    /devorg:status — read-only status report
  hooks/hooks.json                  when the guards run
  scripts/                          what the guards do (devorg_hooks.py + run-hook.sh launcher)
  .mcp.json                         registers the token-tracker MCP server
  mcp/token_tracker.py              the MCP server (token usage per session and agent)
tests/test_hooks.py               29 tests for the guards
tests/test_mcp.py                 9 tests for the MCP server
docs/                             how it works, safety, configuration, testing
docs/history/                     the original proposal
```

## Documentation

- [Architecture](docs/architecture.md) — agents vs subagents, roles, context isolation
- [Workflow](docs/workflow.md) — the 12 steps, the trade-off triangle, gates, rework, records
- [Safety](docs/safety.md) — what is enforced by code, what by instructions, known gaps
- [Configuration](docs/configuration.md) — `config.json`, `rules.md`, permissions
- [Token tracker (MCP)](docs/mcp.md) — how the MCP server works, message by message
- [Testing](docs/testing.md) — running the hook tests, the end-to-end checklist
- [Changelog](CHANGELOG.md)
