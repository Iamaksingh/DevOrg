# Safety

DevOrg separates **what agents are asked to do** (instructions) from **what they are able to do**
(tool lists and hooks). Important rules are enforced by code.

## When the guards are active

| Project state | Guards |
|---|---|
| No `.devorg/config.json` | Off — the plugin does nothing (`run-hook.sh` exits before starting Python) |
| Set up, no ticket running (or ticket `done` / `cancelled`) | Off, except: agents can never write `approvals.json` or the plugin's own files |
| Ticket running | **On** |

## What is enforced by code

| Rule | Mechanism |
|---|---|
| No project edits before Gate A | `guard-edit` requires a human-recorded plan approval and phase `implement` |
| Only the approved developer edits | `guard-edit` compares the hook's `agent_type` with the developer recorded at Gate A (namespaced or bare name). The Manager, the other developers and reviewers are blocked |
| Manager can't swap developers after approval | the approved developer is snapshotted in `approvals.json` at Gate A |
| Only the human approves | `gate` hook writes `approvals.json` from typed keywords; agents are blocked from writing it via Edit/Write or shell |
| Rules/config can't change mid-ticket | `guard-edit` blocks `.devorg/config.json` and `.devorg/rules.md` |
| No edits outside the project | `guard-edit` |
| No secrets | `guard-read` and `guard-edit` block `.env*` (except `.example`/`.sample`/`.template`), private keys, `credentials`, `.ssh/`, `.aws/`, `secrets/`; `guard-bash` blocks commands naming them |
| No push / merge / destructive git | `guard-bash`: push, pull, merge, rebase, cherry-pick, reset --hard, clean -f, checkout --/., restore (unless --staged), remote add/set-url, branch -d |
| No publishing / deploying / network | `guard-bash`: npm/yarn/pnpm/cargo publish, twine upload, docker/podman push, kubectl, helm, terraform apply/destroy, curl, wget, scp, … |
| No recursive or forced deletes | `guard-bash`: `rm -r/-f`, `Remove-Item -Recurse`, `del /s` |
| STOP really stops | `guard-edit` blocks every project edit while stopped |
| Reviewers can't edit | their `tools:` are Read, Grep, Glob only |
| Developers can't run commands | their `tools:` exclude Bash |

If Python can't be found in a DevOrg project, `run-hook.sh` **fails closed** for guards (blocks the
action with an explanation) rather than silently switching protection off.

## What is enforced only by instructions (known gaps)

- **Shell edits by the Manager.** The Manager has Bash, so it could write files with shell
  commands. `guard-bash` blocks the dangerous categories above, and Claude Code asks permission
  for commands that aren't allow-listed, but arbitrary file writes via shell aren't parsed.
- **Command parsing is heuristic.** `guard-bash` splits on `&&`, `||`, `;`, `|` and inspects each
  command; deliberately obfuscated commands (variables, `eval`, scripts) can slip past.
- **Grep can show secret contents.** `guard-read` covers the Read tool. Add
  `"deny": ["Read(**/.env)", "Read(**/.env.*)"]` to your project settings for Claude Code's own
  protection, which also applies to Grep (`/devorg:init` recommends this).
- **Workflow order, the rework limit and the review order** are followed by the Manager's playbook;
  the hooks don't verify them.
- **Ticket and repository content are untrusted.** Agents are told to treat them as data and report
  injection attempts; this is an instruction, not a filter.

## Reporting a bypass

Add a failing case to `tests/test_hooks.py`, fix `scripts/devorg_hooks.py`, and run the suite.
