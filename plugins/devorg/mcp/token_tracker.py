#!/usr/bin/env python3
"""DevOrg token tracker: a small MCP server written with the Python standard library only.

HOW MCP WORKS HERE (read this first)
------------------------------------
Claude Code starts this script as a child process and talks to it through stdin/stdout.
Every message is one line of JSON (JSON-RPC 2.0). Claude Code is the "client", we are the
"server". A session looks like this:

    client -> {"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
    server <- {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":...,"capabilities":{"tools":{}},...}}
    client -> {"jsonrpc":"2.0","method":"notifications/initialized"}        (no id = no reply)
    client -> {"jsonrpc":"2.0","id":2,"method":"tools/list"}
    server <- {"jsonrpc":"2.0","id":2,"result":{"tools":[{name, description, inputSchema}, ...]}}
    client -> {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"session_usage","arguments":{}}}
    server <- {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"..."}]}}

Rules: stdout carries ONLY protocol messages (anything else breaks the connection), so all
logging goes to stderr. Requests have an "id" and need exactly one reply; notifications have
no "id" and get no reply.

WHERE THE NUMBERS COME FROM
---------------------------
Claude Code saves every conversation under ~/.claude/projects/<project-folder-slug>/:
    <session-id>.jsonl                                main conversation, one JSON object per line
    <session-id>/subagents/agent-<id>.jsonl           one file per subagent run
    <session-id>/subagents/agent-<id>.meta.json       {"agentType": "devorg:developer-2", ...}
Each assistant reply line has message.usage = {input_tokens, output_tokens,
cache_creation_input_tokens, cache_read_input_tokens}. One reply can be split over several
lines that repeat the same message.id and usage, so we count each message.id once.
This file format is not officially documented and may change in future Claude Code versions.

The server is read-only: it never writes or deletes anything.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVER_NAME = "devorg-token-tracker"
SERVER_VERSION = "0.2.0"
SUPPORTED_PROTOCOLS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

TOKEN_FIELDS = ("input", "cache_write", "cache_read", "output")


def log(*parts):
    """Debug output. Must go to stderr: stdout is reserved for the protocol."""
    print(SERVER_NAME + ":", *parts, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------
# Part 1: reading Claude Code's transcript files
# --------------------------------------------------------------------------------------

def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def project_dir():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def slug(path):
    """Claude Code names a project's transcript folder by replacing every character that
    is not a letter or digit with '-':  C:\\work\\my.app  ->  C--work-my-app"""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def transcripts_dir():
    """Folder holding this project's transcripts, or None if there are none yet."""
    projects = claude_home() / "projects"
    wanted = slug(project_dir())
    if (projects / wanted).is_dir():
        return projects / wanted
    if projects.is_dir():  # drive letters may differ in case on Windows (c: vs C:)
        for child in projects.iterdir():
            if child.is_dir() and child.name.lower() == wanted.lower():
                return child
    return None


def empty_totals():
    return {field: 0 for field in TOKEN_FIELDS}


def add(totals, other):
    for field in TOKEN_FIELDS:
        totals[field] += other[field]
    return totals


def total_of(totals):
    return sum(totals[field] for field in TOKEN_FIELDS)


def read_usage(jsonl_path):
    """Sum the token usage in one transcript file.
    Returns (totals, by_model, first_timestamp, last_timestamp)."""
    per_message = {}  # message.id -> (model, usage); the last copy of each reply wins
    first = last = None
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue  # a half-written last line while the session is running
                stamp = entry.get("timestamp")
                if stamp:
                    first = first or stamp
                    last = stamp
                message = entry.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                    continue
                key = message.get("id") or entry.get("uuid") or len(per_message)
                per_message[key] = (message.get("model") or "unknown", message["usage"])
    except OSError as exc:
        log("cannot read", jsonl_path, exc)

    totals, by_model = empty_totals(), {}
    for model, usage in per_message.values():
        one = {
            "input": usage.get("input_tokens") or 0,
            "cache_write": usage.get("cache_creation_input_tokens") or 0,
            "cache_read": usage.get("cache_read_input_tokens") or 0,
            "output": usage.get("output_tokens") or 0,
        }
        add(totals, one)
        add(by_model.setdefault(model, empty_totals()), one)
    return totals, by_model, first, last


def agent_type(meta_path):
    try:
        with open(meta_path, encoding="utf-8") as fh:
            return json.load(fh).get("agentType") or "unknown"
    except (OSError, ValueError):
        return "unknown"


def session_report(folder, session_id):
    """Usage of one session: the main conversation plus every subagent it started."""
    main, models, first, last = read_usage(folder / (session_id + ".jsonl"))
    parts = [{"agent": "main session", "tokens": main}]
    total = dict(main)
    sub_dir = folder / session_id / "subagents"
    if sub_dir.is_dir():
        for path in sorted(sub_dir.glob("agent-*.jsonl")):
            tokens, sub_models, _, sub_last = read_usage(path)
            parts.append({"agent": agent_type(path.with_suffix(".meta.json")), "tokens": tokens})
            add(total, tokens)
            for model, counts in sub_models.items():
                add(models.setdefault(model, empty_totals()), counts)
            if sub_last and (not last or sub_last > last):
                last = sub_last
    return {"session": session_id, "first": first, "last": last,
            "parts": parts, "total": total, "models": models}


def sessions_newest_first(folder):
    files = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in files]


# --------------------------------------------------------------------------------------
# Part 2: formatting (tools return plain text; markdown tables read well in Claude Code)
# --------------------------------------------------------------------------------------

def k(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def table(rows):
    """rows: list of (label, totals). Adds a TOTAL row."""
    out = ["| Agent | Runs | Input | Cache write | Cache read | Output | Total |",
           "|---|---|---|---|---|---|---|"]
    grand, runs_total = empty_totals(), 0
    for label, runs, t in rows:
        out.append(f"| {label} | {runs} | {k(t['input'])} | {k(t['cache_write'])} | "
                   f"{k(t['cache_read'])} | {k(t['output'])} | {k(total_of(t))} |")
        add(grand, t)
        runs_total += runs
    out.append(f"| **TOTAL** | {runs_total} | {k(grand['input'])} | {k(grand['cache_write'])} | "
               f"{k(grand['cache_read'])} | {k(grand['output'])} | **{k(total_of(grand))}** |")
    return "\n".join(out)


def grouped(parts):
    """Merge parts with the same agent name: [(agent, runs, totals)], biggest first."""
    groups = {}
    for part in parts:
        runs, totals = groups.setdefault(part["agent"], [0, empty_totals()])
        groups[part["agent"]][0] = runs + 1
        add(totals, part["tokens"])
    return sorted(((name, r, t) for name, (r, t) in groups.items()),
                  key=lambda row: total_of(row[2]), reverse=True)


NOTE = ("\n\nCache read = context re-used from earlier turns (billed far cheaper than input). "
        "Counts are tokens, not money.")


# --------------------------------------------------------------------------------------
# Part 3: the tools. Each has a name, a description (Claude reads it to decide when to
# call the tool), a JSON Schema for its arguments, and a Python function.
# --------------------------------------------------------------------------------------

class ToolError(Exception):
    """A problem the caller should see (bad argument, no data). Not a server crash."""


def need_folder():
    folder = transcripts_dir()
    if folder is None:
        raise ToolError(f"No Claude Code transcripts found for {project_dir()}.")
    return folder


def tool_list_sessions(args):
    limit = int(args.get("limit", 10))
    if not 1 <= limit <= 100:
        raise ToolError("limit must be between 1 and 100")
    folder = need_folder()
    lines = ["| Session | Started | Last activity | Subagents | Total tokens |",
             "|---|---|---|---|---|"]
    for session_id in sessions_newest_first(folder)[:limit]:
        r = session_report(folder, session_id)
        lines.append(f"| {session_id} | {r['first'] or '?'} | {r['last'] or '?'} | "
                     f"{len(r['parts']) - 1} | {k(total_of(r['total']))} |")
    return "\n".join(lines)


def tool_session_usage(args):
    folder = need_folder()
    session_id = args.get("session_id") or "latest"
    if session_id == "latest":
        sessions = sessions_newest_first(folder)
        if not sessions:
            raise ToolError("This project has no sessions yet.")
        session_id = sessions[0]
    if not re.fullmatch(r"[A-Za-z0-9-]+", session_id) or \
            not (folder / (session_id + ".jsonl")).is_file():
        raise ToolError(f"Unknown session: {session_id}. Use list_sessions to see valid ids.")
    r = session_report(folder, session_id)
    models = "\n".join(f"- {m}: {k(total_of(t))}" for m, t in r["models"].items())
    return (f"Session {session_id} ({r['first']} to {r['last']})\n\n"
            f"{table(grouped(r['parts']))}\n\nBy model:\n{models}{NOTE}")


def tool_usage_by_agent(args):
    days = int(args.get("days", 7))
    if not 1 <= days <= 365:
        raise ToolError("days must be between 1 and 365")
    folder = need_folder()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    parts, count = [], 0
    for session_id in sessions_newest_first(folder):
        mtime = datetime.fromtimestamp((folder / (session_id + ".jsonl")).stat().st_mtime,
                                       timezone.utc)
        if mtime < cutoff:
            break  # newest first, so everything after this is older
        parts.extend(session_report(folder, session_id)["parts"])
        count += 1
    if not parts:
        return f"No sessions in the last {days} days."
    return (f"Last {days} days, {count} session(s), all agents combined:\n\n"
            f"{table(grouped(parts))}{NOTE}")


TOOLS = {
    "list_sessions": {
        "description": "List recent Claude Code sessions in this project with their total "
                       "token usage, newest first. Use it to find a session id.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100,
                                     "description": "How many sessions (default 10)"}},
        },
        "run": tool_list_sessions,
    },
    "session_usage": {
        "description": "Token usage of one session, split by agent (main session, and each "
                       "subagent type such as devorg:developer-2) and by model. Use it to see "
                       "which agents consumed the most tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string",
                                          "description": "Session id, or 'latest' (default)"}},
        },
        "run": tool_session_usage,
    },
    "usage_by_agent": {
        "description": "Total token usage per agent type across all sessions of this project "
                       "in the last N days.",
        "inputSchema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 365,
                                    "description": "How far back to look (default 7)"}},
        },
        "run": tool_usage_by_agent,
    },
}


# --------------------------------------------------------------------------------------
# Part 4: the protocol. Read a line, work out what the client wants, write a line back.
# --------------------------------------------------------------------------------------

def handle(request):
    """Return the 'result' for a request, or raise RpcError."""
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        asked = params.get("protocolVersion")
        return {
            # Agree on a protocol version: the client's if we know it, else our newest.
            "protocolVersion": asked if asked in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0],
            "capabilities": {"tools": {}},  # we offer tools (no resources or prompts)
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [{"name": name, "description": t["description"],
                           "inputSchema": t["inputSchema"]} for name, t in TOOLS.items()]}
    if method == "tools/call":
        tool = TOOLS.get(params.get("name"))
        if tool is None:
            raise RpcError(-32602, f"Unknown tool: {params.get('name')}")
        try:
            text = tool["run"](params.get("arguments") or {})
            return {"content": [{"type": "text", "text": text}]}
        except (ToolError, ValueError, TypeError) as exc:
            # A failed tool is still a successful protocol reply, flagged with isError,
            # so Claude sees the message and can try again differently.
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    raise RpcError(-32601, f"Method not found: {method}")


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def main():
    # The protocol is UTF-8 on every OS (Windows would otherwise default to its code page).
    sys.stdin.reconfigure(encoding="utf-8-sig")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    log("started; project =", project_dir())
    for line in sys.stdin:  # ends when Claude Code closes stdin (session over)
        line = line.lstrip("﻿")  # tolerate a byte-order mark from some shells
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except ValueError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        if "id" not in request:
            continue  # a notification such as notifications/initialized: no reply allowed
        reply = {"jsonrpc": "2.0", "id": request["id"]}
        try:
            reply["result"] = handle(request)
        except RpcError as exc:
            reply["error"] = {"code": exc.code, "message": str(exc)}
        except Exception as exc:  # never crash the server on one bad request
            log("internal error:", repr(exc))
            reply["error"] = {"code": -32603, "message": "Internal error"}
        send(reply)


if __name__ == "__main__":
    main()
