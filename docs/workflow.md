# Workflow

The authoritative, step-by-step version is the Manager's playbook,
[`plugins/devorg/skills/run/SKILL.md`](../plugins/devorg/skills/run/SKILL.md). This page explains it.

## The 12 steps

| # | Step | Who | Output |
|---|---|---|---|
| 1 | Ticket submitted | Human | `00-ticket.md` |
| 2 | Analyse | Ticket Reviewer | **complexity rating**, requirements, open questions (with defaults), acceptance criteria, **Context brief** |
| 3 | Design | System Architect | design, constraints (+ **trade-off triangle + weights** on complex) |
| 4 | Propose | Developer 1, or Developers 1–3 in parallel (complex) | proposals |
| 5 | Decide | Manager | baseline gate (+ weighted scores, SELECT or HYBRID on complex) |
| 6 | **Gate A** | Human | `APPROVE PLAN` / `REJECT PLAN <reason>` |
| 7 | Implement / rework | Selected developer | code + tests |
| 7b | **Checks** + diff | Manager | build/lint/test output, diff. Failing checks go back to step 7, no reviewer runs |
| 8–10 | Verification | Senior Developer `MODE VERIFY` (trivial, standard) · Architect + Senior Developer + Ticket Reviewer in parallel (complex) | `VERDICT: PASS/FAIL` + findings, acceptance table |
| 11 | **Gate B** | Human | `APPROVE FINAL` / `REJECT FINAL <reason>` |
| 12 | Done | Manager | `final-report.md`, optional local commit |

## Tracks: matching the team to the ticket

Running six agents on a colour change wastes tokens and time. The Ticket Reviewer rates every
ticket, and the rating picks the **track**:

| | trivial | standard | complex |
|---|---|---|---|
| Example | fix a typo, change a colour, off-by-one in one file | add a filter to an API endpoint | new module, schema change, cross-service feature |
| Design | — | ✓ | ✓ with triangle |
| Proposals | Developer 1 (`CORNER: Simplicity`) | Developer 1 (`CORNER: none`) | Developers 1–3, one corner each |
| Verification | Senior Developer `MODE VERIFY` | Senior Developer `MODE VERIFY` | 3 reviews in parallel |
| Agent calls (no rework) | 4 | 5 | 9–10 |

Safety rules for the rating:
- **Sensitive areas** (auth, input validation, secrets/crypto, database schema or migrations,
  payments, public API contracts) make a ticket at least standard. When in doubt, higher.
- The Manager may raise the track (e.g. when the Architect writes `TRACK CONCERN`), never lower it.
- The human decides in the end: `/devorg:run "…" --track complex` at the start, or
  `REJECT PLAN track: complex` at Gate A.
- Both gates and all hooks apply on every track.

## Fewer tokens per agent

- **Context brief:** the Ticket Reviewer is the only agent that searches the whole repository. Its
  analysis ends with the relevant files, key code, conventions and commands. Architect and
  developers start from it and list any extra file they read, with a reason. Reviewers may read
  anything; an independent review must not be limited to what the developer was shown.
- **Model per role** (the `model:` line in each agent file): reasoning-heavy roles run on opus
  (System Architect, Senior Developer); the Ticket Reviewer and developers run on sonnet. The
  Manager uses whatever model you chose for the session; running the session on Sonnet is a
  valid way to cut cost further.
- **Checks before reviews:** build, lint and tests (`check_commands` + `test_command`) must pass
  before any reviewer is called, so no reviewer tokens are spent on code that doesn't build.
- **Parallel reviews, one rework:** on complex tickets the three reviews run at the same time and
  all findings go back to the developer in one rework round.

Use the token tracker (`session_usage`) to compare the same ticket on different tracks.

## The trade-off triangle (complex tickets)

Good engineering qualities pull against each other: more of one usually costs some of another.
For each ticket the Architect names three qualities that genuinely conflict **for this ticket**:

| Ticket type | Typical triangle |
|---|---|
| Small feature / CLI / script | Simplicity · Robustness · Extensibility |
| API / backend service | Latency · Consistency · Cost |
| Distributed data / sync | Consistency · Availability · Partition tolerance (CAP) |
| UI / frontend | Speed to ship · Accessibility · Flexibility |
| Data pipeline | Freshness · Accuracy · Cost |

…and a **weight** (1 normal, 2 important, 3 critical) for each, justified from the ticket.
Developer *n* leans toward corner *n*.

**The baseline** keeps every developer good: correct, safe, tested, compliant with constraints,
consistent with the codebase. A corner is what a developer optimises *above* that floor — never
instead of it. Correctness and security are never corners.

**The decision (step 5):**
1. Baseline gate — a proposal that fails it is out.
2. Every proposal is scored 1–5 on **all three** corners.
3. Weighted total = Σ weight × score.
4. `SELECT` one proposal, or `HYBRID`: a base proposal + at most 2 grafts from the others, which the
   Architect checks for coherence. The base developer implements the whole plan.

At Gate A the human sees the triangle, weights and scores, and can change the weights
(`REJECT PLAN weights: robustness 3, simplicity 1`), which re-runs the comparison.

## Gates

Approvals count only when the **human types** the keyword at the start of a message, in
uppercase. The gate hook records it in `.devorg/approvals.json` (agents can't write that file);
the Manager then reads the file. A keyword typed in the wrong phase is recorded as ignored.

| Keyword | Valid when | Effect |
|---|---|---|
| `APPROVE PLAN [notes]` | awaiting plan approval | records approval + the approved developer; edits become possible in step 7 |
| `REJECT PLAN <reason>` | awaiting plan approval | back to step 5 (or 3/4 if asked; `track: <level>` switches track) |
| `APPROVE FINAL` | awaiting final approval | step 12 |
| `REJECT FINAL <reason>` | awaiting final approval | back to step 7, then checks and every review of the track again |
| `STOP` | any time during a ticket | freezes all project edits |
| `RESUME` | after STOP | continues |
| `CANCEL` | any time during a ticket | closes the ticket; guards switch off |

## Rework loop

Failed checks, or one or more failed reviews, send the work back to step 7 with **all** findings
in one rework round. After the fix and green checks, **only the failed reviews run again**. Each
stage (checks, verify, architecture, code, acceptance) has its own counter; when one reaches
`max_revisions` (default 3) the Manager stops and asks the human.

## Records

```
.devorg/tickets/<ID>/
  00-ticket.md  01-analysis.md  02-design.md
  03-proposals/developer-<n>.md
  04-decision.md  04-hybrid-check.md
  05-implementation/round-<n>-summary.md  round-<n>.diff  round-<n>-checks.txt
  06-reviews/verify-r<n>.md  or  {architecture,code,acceptance}-r<n>.md
  log.md  final-report.md
```

`state.json` (single source of truth for the workflow) and `approvals.json` sit in `.devorg/`.
