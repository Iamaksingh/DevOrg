---
name: status
description: Show where the current DevOrg ticket stands — phase, selected developer, rework counts, approvals and the next expected action. Read-only.
---

Report the status of DevOrg in this project. **Read only — change nothing.**

1. If `.devorg/config.json` doesn't exist: say DevOrg isn't set up here and suggest `/devorg:init`. Stop.
2. Read `.devorg/state.json`. If it doesn't exist, say no ticket has run yet. Otherwise also read
   `.devorg/approvals.json` (the entry for this ticket) and the last ~10 lines of
   `.devorg/tickets/<ID>/log.md`.
3. Reply with a compact block:

```
Ticket:     <ID> — <title from 00-ticket.md>
Track:      <trivial|standard|complex>  (older tickets without a track: complex)
Phase:      <phase>  (step <n> of 12)
Decision:   <SELECT|HYBRID> · implementer: <developer> · grafts: <n>
Rework:     checks <n>/<max> · then, per review stage used by the track:
            verify <n>/<max>  |  architecture <n>/<max> · code <n>/<max> · acceptance <n>/<max>
Approvals:  plan <approved|rejected|pending> (<time>) · final <…>
Stopped:    yes (<time>) | no
Last event: <last log line>
Next:       <what happens next / what the human must type>
Tokens:     <total for this session> (biggest: <agent> <n>)
```

For the Tokens line, call the `mcp__plugin_devorg_token-tracker__session_usage` tool with no
arguments. If it is unavailable, write `Tokens: unavailable`.

Phase → next action:
- `awaiting_plan_approval` → human types `APPROVE PLAN`, `REJECT PLAN <reason>` or `STOP`.
- `awaiting_final_approval` → human types `APPROVE FINAL`, `REJECT FINAL <reason>` or `STOP`.
- `stopped` → human types `RESUME` or `CANCEL`.
- `done` / `cancelled` → start a new ticket with `/devorg:run`.
- anything else → `/devorg:run resume` continues from here.
