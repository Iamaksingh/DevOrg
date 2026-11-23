# The token tracker: how an MCP server is integrated

DevOrg ships one small MCP server, `token-tracker`, which reports how many tokens each agent used.
It was written by hand (no MCP library) so every part of the integration is visible.

## What MCP is

**MCP (Model Context Protocol)** is a standard way to give Claude new tools. A tool is
something Claude can call, like `Read` or `Bash`, but provided by a separate program, the
**MCP server**. Claude Code is the **MCP client**.

```
 ┌──────────── Claude Code (client) ────────────┐        ┌──── token_tracker.py (server) ────┐
 │ Claude decides to call session_usage         │ stdin  │ reads ~/.claude/projects/...      │
 │   → sends  {"method":"tools/call", ...}      │ ─────► │ adds up the usage numbers         │
 │   ← gets   {"result":{"content":[text]}}     │ ◄───── │ replies with a markdown table     │
 └──────────────────────────────────────────────┘ stdout └───────────────────────────────────┘
```

Without MCP, Claude can't see token usage at all. With it, Claude can answer "which agent cost
the most?" by calling a tool.

## Step 1: register the server (`plugins/devorg/.mcp.json`)

```json
{ "mcpServers": { "token-tracker": {
    "command": "python",
    "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/token_tracker.py"] } } }
```

When the plugin is enabled, Claude Code runs `python <plugin folder>/mcp/token_tracker.py` as a
child process at the start of the session and keeps it running. `${CLAUDE_PLUGIN_ROOT}` is
replaced with the plugin's installed folder. Claude Code also sets `CLAUDE_PROJECT_DIR` in the
server's environment, which is how the server knows which project's transcripts to read.

The server is called `token-tracker` in the file, `plugin:devorg:token-tracker` in `/mcp`, and its
tools are named `mcp__plugin_devorg_token-tracker__<tool>`, the name used in permission rules.

> On macOS/Linux where only `python3` exists, change `"command"` to `"python3"`.

## Step 2: the conversation (JSON-RPC over stdin/stdout)

Every message is one line of JSON. Messages with an `id` are **requests** and need exactly one
reply with the same `id`. Messages without an `id` are **notifications** and get no reply.

| # | Client sends | Server replies | Meaning |
|---|---|---|---|
| 1 | `initialize` + its protocol version | protocol version, `capabilities: {tools: {}}`, name | "Hello, I offer tools" |
| 2 | `notifications/initialized` | nothing | "Ready" |
| 3 | `tools/list` | 3 tools, each with name, description, JSON Schema of arguments | the menu |
| 4 | `tools/call` `{name, arguments}` | `{content: [{type: "text", text}]}` | run one tool |

The **description** in `tools/list` matters: it's all Claude reads when deciding whether a tool
fits the user's question. The **inputSchema** tells Claude which arguments are allowed.

Two kinds of failure:
- **Protocol error** (unknown method, unknown tool): an `error` object, e.g. code `-32601`.
- **Tool error** (bad session id, no data): a normal result with `"isError": true`. Claude sees
  the message and can correct itself, e.g. by calling `list_sessions` first.

Rule that breaks most first servers: **stdout is only for protocol messages.** A stray `print()`
corrupts the stream, so all logging goes to stderr.

You can try it without Claude. In PowerShell, from the repo root:

```powershell
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}',
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"session_usage","arguments":{}}}' |
  python plugins/devorg/mcp/token_tracker.py
```

## Step 3: where the numbers come from

Claude Code saves every conversation under `~/.claude/projects/<project path with every
non-alphanumeric character replaced by '-'>/`:

```
<session-id>.jsonl                          main conversation, one JSON object per line
<session-id>/subagents/agent-<id>.jsonl     one file per subagent run
<session-id>/subagents/agent-<id>.meta.json {"agentType": "devorg:developer-2", ...}
```

Each assistant reply has `message.usage`: `input_tokens`, `output_tokens`,
`cache_creation_input_tokens` (shown as *cache write*) and `cache_read_input_tokens`. One reply
can appear on several lines with the same `message.id`, so the server counts each id once.

*Cache read* is usually the biggest number: every turn re-sends the conversation so far, and
the cached part is billed at a fraction of the normal input price. Figures are tokens, not
money, because prices differ by model and change over time.

**Caveat:** this file format is Claude Code's internal format, not a documented API. An update
could change it. If the numbers ever look wrong, check a transcript line first.

## Step 4: who uses it

- **You**, in any project: ask "how many tokens did this session use, by agent?"
- **The Manager** (`/devorg:run`) at Gate A, at Gate B and in `final-report.md`.
- **`/devorg:status`** shows the session total.

The first call asks for permission like any tool. To allow it permanently, add
`"mcp__plugin_devorg_token-tracker__*"` to `permissions.allow`. It's safe: the server only reads.

## The tools

| Tool | Arguments | Returns |
|---|---|---|
| `list_sessions` | `limit` (1–100, default 10) | recent sessions with start, last activity, subagent count, total |
| `session_usage` | `session_id` (default `latest`) | table by agent + totals by model |
| `usage_by_agent` | `days` (1–365, default 7) | table by agent type across sessions |

## Ideas to extend it (good exercises)

1. **Cost estimate:** a `prices` table in `.devorg/config.json` and an `estimate_cost` tool.
2. **Per ticket:** record the session id in `state.json` so `ticket_usage(ticket_id)` works
   across `resume`d sessions.
3. **Budget:** a `budget_status` tool the Manager calls before the 3 parallel proposals.
4. **Rewrite it with the official SDK** (`pip install mcp`, `FastMCP`) and compare: the whole of
   Part 4 in `token_tracker.py` becomes a few decorators.
