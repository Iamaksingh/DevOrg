# Configuration

Everything project-specific lives in the project's `.devorg/` folder (git-ignored), created by
`/devorg:init`. The plugin itself contains nothing project-specific.

## `.devorg/config.json`

```json
{
  "version": 1,
  "check_commands": ["npm --prefix frontend run build", "npm --prefix backend run lint"],
  "test_command": "npm --prefix backend test",
  "max_revisions": 3
}
```

| Field | Meaning |
|---|---|
| `version` | Config format version (currently 1) |
| `check_commands` | Optional list of cheap checks (build, lint, type check) run **in order before the tests**, after every implementation round. If one fails, the work goes straight back to the developer and no reviewer is called. `/devorg:init` suggests scripts it finds |
| `test_command` | Command the Manager runs from the project root after the check commands. `/devorg:init` suggests one from the project's files (npm, pytest, go, cargo, maven, gradle, dotnet, rspec, make) and you confirm it. If the project has no tests yet, use a check that passes (e.g. `node --check app.js`) and make your first ticket "add tests" |
| `max_revisions` | Rework cycles allowed per stage (checks, verify, architecture, code, acceptance) before the Manager stops and asks you |

Configs from 0.2.0 without `check_commands` keep working (only `test_command` runs).

## Choosing the track yourself

DevOrg rates each ticket trivial, standard or complex and runs fewer agents on simpler tickets
(see [workflow](workflow.md#tracks-matching-the-team-to-the-ticket)). To override:

```
/devorg:run "Add rate limiting to the login endpoint" --track complex
```

or reply `REJECT PLAN track: complex` at Gate A.

## Models

Each agent file sets its model (`model:` in `plugins/devorg/agents/*.md`): opus for the System
Architect and Senior Developer, sonnet for the Ticket Reviewer and developers. Edit those lines
in your copy of the plugin to change it. The Engineering Manager runs on the model you choose for
your Claude Code session.

The file's existence is also the **on switch**: without it the plugin's hooks do nothing.
It can't be changed by agents while a ticket is running.

## `.devorg/rules.md`

The organisation rules every agent follows: roles, workflow, trade-off triangle, developer
baseline, safety rules and output conventions. `/devorg:init` copies it from the plugin's
template (`skills/init/org-rules.md`). Your team may tailor it — e.g. add "all public functions
need docstrings" to the baseline. Agents can't change it while a ticket is running. Re-running
`/devorg:init --force` asks before replacing a tailored copy.

The project's own `CLAUDE.md` still applies; subagents load it automatically, and the baseline
requires consistency with the project's conventions.

## Recommended project permissions (optional)

In `.claude/settings.local.json` (personal) or `.claude/settings.json` (shared):

```json
{
  "permissions": {
    "allow": ["Bash(npm test:*)"],
    "deny": ["Read(**/.env)", "Read(**/.env.*)"]
  }
}
```

The allow rule stops test runs from asking each time; the deny rules add Claude Code's own
secrets protection (which also covers Grep) on top of DevOrg's guards.

## Enabling per project

Install the plugin once (`/plugin install devorg@devorg-marketplace`). With user scope it is
available everywhere but stays inactive until `/devorg:init` runs in a project. To enable it only
for one project, install it with project scope from the `/plugin` menu.

## Using DevOrg on a non-Python project

Nothing changes except `test_command`. The hooks need Python 3.8+ on the machine, but the
project itself can be in any language.
