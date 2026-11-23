# Configuration

Everything project-specific lives in the project's `.devorg/` folder (git-ignored), created by
`/devorg:init`. The plugin itself contains nothing project-specific.

## `.devorg/config.json`

```json
{
  "version": 1,
  "test_command": "npm test",
  "max_revisions": 3
}
```

| Field | Meaning |
|---|---|
| `version` | Config format version (currently 1) |
| `test_command` | Command the Manager runs from the project root after every implementation round. `/devorg:init` suggests one from the project's files (npm, pytest, go, cargo, maven, gradle, dotnet, rspec, make) and you confirm it |
| `max_revisions` | Rework cycles allowed per stage (tests, architecture, code, acceptance) before the Manager stops and asks you |

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
