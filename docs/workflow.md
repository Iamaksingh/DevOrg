# Workflow

The authoritative, step-by-step version is the Manager's playbook,
[`plugins/devorg/skills/run/SKILL.md`](../plugins/devorg/skills/run/SKILL.md). This page explains it.

## The 12 steps

| # | Step | Who | Output |
|---|---|---|---|
| 1 | Ticket submitted | Human | `00-ticket.md` |
| 2 | Analyse | Ticket Reviewer | requirements, assumptions, open questions (with defaults), acceptance criteria |
| 3 | Design | System Architect | design, constraints, **trade-off triangle + weights** |
| 4 | Propose (parallel) | Developers 1–3 | one proposal each, one corner each |
| 5 | Compare | Manager | baseline gate, weighted scores, SELECT or HYBRID |
| 6 | **Gate A** | Human | `APPROVE PLAN` / `REJECT PLAN <reason>` |
| 7 | Implement / rework | Selected developer | code + tests |
| 7b | Test run + diff | Manager | test output, diff |
| 8 | Architecture review | System Architect | `VERDICT: PASS/FAIL` + findings |
| 9 | Code review | Senior Developer | `VERDICT: PASS/FAIL` + findings |
| 10 | Acceptance review | Ticket Reviewer | each criterion MET/NOT MET with evidence |
| 11 | **Gate B** | Human | `APPROVE FINAL` / `REJECT FINAL <reason>` |
| 12 | Done | Manager | `final-report.md`, optional local commit |

## The trade-off triangle

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
| `REJECT PLAN <reason>` | awaiting plan approval | back to step 5 (or 3/4 if asked) |
| `APPROVE FINAL` | awaiting final approval | step 12 |
| `REJECT FINAL <reason>` | awaiting final approval | back to step 7, then all three reviews again |
| `STOP` | any time during a ticket | freezes all project edits |
| `RESUME` | after STOP | continues |
| `CANCEL` | any time during a ticket | closes the ticket; guards switch off |

## Rework loop

A failed test run or review sends the work back to step 7 with the findings. After the fix and a
green test run, the **failed review runs again, then the later ones**. Each stage (tests,
architecture, code, acceptance) has its own counter; when one reaches `max_revisions` (default 3)
the Manager stops and asks the human.

## Records

```
.devorg/tickets/<ID>/
  00-ticket.md  01-analysis.md  02-design.md
  03-proposals/developer-{1,2,3}.md
  04-decision.md  04-hybrid-check.md
  05-implementation/round-<n>-summary.md  round-<n>.diff  round-<n>-tests.txt
  06-reviews/{architecture,code,acceptance}-r<n>.md
  log.md  final-report.md
```

`state.json` (single source of truth for the workflow) and `approvals.json` sit in `.devorg/`.
