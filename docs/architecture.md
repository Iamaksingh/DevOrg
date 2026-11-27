# Architecture

## The roles

| Role | Type | Model | Tools | Defined in |
|---|---|---|---|---|
| Engineering Manager | **main session** | session's | all (delegates; edits only `.devorg/`) | `skills/run/SKILL.md` |
| Ticket Reviewer | subagent | sonnet | Read, Grep, Glob | `agents/ticket-reviewer.md` |
| System Architect | subagent | opus | Read, Grep, Glob | `agents/system-architect.md` |
| Developer 1 / 2 / 3 | subagents | sonnet | Read, Grep, Glob, Edit, Write | `agents/developer-{1,2,3}.md` |
| Senior Developer | subagent | opus | Read, Grep, Glob | `agents/senior-developer.md` |
| Security Reviewer | subagent (optional) | opus; re-checks on sonnet | Read, Grep, Glob | `agents/security-reviewer.md` |

Models follow cognitive load: design and code review (where a miss is expensive) get opus;
analysis, proposals and implementation against a design get sonnet.

### Why the Manager is not a subagent

A subagent runs to completion and returns one result; it cannot stop halfway and wait for a
human. The Manager has to pause at two approval gates, so it runs as the **main session**:
`/devorg:run` loads its playbook into the conversation. The seven specialists are true subagents,
spawned by the Manager with the Agent tool as `devorg:<name>`.

### Why three developer files that look the same

The developers are deliberately identical except for their name. Their difference — which corner
of the trade-off triangle they optimise — is assigned per ticket by the Manager. They still need
separate files because each must be a separate agent so that (a) the three can run in parallel
and (b) the edit guard can tell which developer is editing (`agent_type` in the hook input).

## Delegation and context isolation

Every subagent starts with an empty context. It knows only:
- its own agent file (role, modes, output format),
- `.devorg/rules.md` (organisation rules, read at start),
- the project's own `CLAUDE.md` (loaded automatically for subagents),
- what the Manager puts in the prompt — the mode, the ticket id and **paths** of record files.

The Manager passes paths rather than pasted text, so each agent reads exactly the evidence it
needs. The Ticket Reviewer's **Context brief** (end of `01-analysis.md`) is the shared starting
point for designers and developers, so they don't each search the repository again; reviewers
keep full read access so their check stays independent. Developers proposing in parallel are never given each other's proposals; the Manager logs
which files each received, as evidence that the proposals are independent.

## Sequential and parallel execution

```mermaid
flowchart TD
    H[Human] -->|/devorg:run ticket| M[Engineering Manager · main session]
    M --> TR[Ticket Reviewer · ANALYSE + complexity + context brief]
    TR -->|trivial| P1[Developer 1 · Simplicity]
    TR -->|standard| SS[System Architect · DESIGN]
    SS --> P1S[Developer 1 · no corner]
    TR -->|complex| SA[System Architect · DESIGN + triangle]
    SA --> D1[Developer 1 · corner 1]
    SA --> D2[Developer 2 · corner 2]
    SA --> D3[Developer 3 · corner 3]
    D1 & D2 & D3 --> C[Manager · baseline gate, weighted scores, SELECT / HYBRID]
    P1 & P1S --> C1[Manager · baseline gate]
    C & C1 --> GA{{Gate A · human types APPROVE PLAN}}
    GA -->|approved| I[Selected developer · IMPLEMENT / REWORK]
    I --> T[Manager runs build, lint, tests + diff]
    T -->|fail| I
    T -->|pass| PS[Manager · security pre-scan, may ask the human]
    PS -->|security on| S[Security Reviewer · SECURITY, re-checks on sonnet]
    S -->|critical / high, max 2 reworks| I
    S -->|pass, or limit reached| SD[Senior Developer · VERIFY or REVIEW]
    PS -->|security off| SD
    PS -->|complex, in parallel| R[Architect REVIEW ‖ Ticket Reviewer ACCEPT]
    SD -->|fail| I
    R -->|any fail, one rework| I
    SD & R --> GB{{Gate B · human types APPROVE FINAL}}
    GB -->|rejected| I
    GB -->|approved| DONE[Done · final report, optional local commit]
```

Parallel stages (several Agent calls in one message): the three proposals and the reviews, both
on complex tickets only — the Architect and Ticket Reviewer run alongside the Security Reviewer,
and the Senior Developer follows once security passes. Everything else is sequential. Cheap shell checks (build, lint,
tests) always run before any reviewer, so a broken build never costs reviewer tokens.

## Enforcement layer

Instructions say what agents *should* do; hooks make the important rules *true*. The plugin
registers four hook entry points (`hooks/hooks.json`), all handled by `scripts/devorg_hooks.py`
via the `scripts/run-hook.sh` launcher. See [safety.md](safety.md).

## Where state lives

| What | Where | Written by |
|---|---|---|
| Project settings | `.devorg/config.json` | `/devorg:init` |
| Organisation rules | `.devorg/rules.md` | `/devorg:init` (team may edit) |
| Workflow state | `.devorg/state.json` | Manager |
| Human decisions | `.devorg/approvals.json` | gate hook only |
| Ticket records | `.devorg/tickets/<ID>/` | Manager |

`.devorg/` is git-ignored. See [workflow.md](workflow.md) for the record files.
