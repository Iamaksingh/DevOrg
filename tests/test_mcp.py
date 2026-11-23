"""Tests for the token-tracker MCP server (plugins/devorg/mcp/token_tracker.py).

Each test builds a fake ~/.claude folder with hand-written transcripts, starts the server as
a child process (exactly as Claude Code does), speaks JSON-RPC to it over stdin/stdout and
checks the replies. Run:  python tests/test_mcp.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / "plugins" / "devorg" / "mcp" / "token_tracker.py"

INIT = {"jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "0"}}}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def reply(model, msg_id, inp, out, cache_write=0, cache_read=0, stamp="2026-01-01T10:00:00Z"):
    return {"type": "assistant", "timestamp": stamp,
            "message": {"id": msg_id, "model": model, "role": "assistant",
                        "usage": {"input_tokens": inp, "output_tokens": out,
                                  "cache_creation_input_tokens": cache_write,
                                  "cache_read_input_tokens": cache_read}}}


def write_jsonl(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


class TokenTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "claude-home"
        self.project = root / "my.project"
        self.project.mkdir()
        folder = self.home / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.project))

        # Main session: message m1 is split over two lines (same id) and must count once.
        write_jsonl(folder / "s1.jsonl", [
            {"type": "user", "timestamp": "2026-01-01T09:59:00Z", "message": {"role": "user"}},
            reply("model-a", "m1", 100, 50, cache_write=1000),
            reply("model-a", "m1", 100, 50, cache_write=1000),
            reply("model-a", "m2", 10, 5, cache_read=2000, stamp="2026-01-01T10:05:00Z"),
        ])
        subagents = folder / "s1" / "subagents"
        for agent_id, agent, out in (("a1", "devorg:developer-2", 300), ("a2", "devorg:developer-2", 200),
                                     ("a3", "devorg:system-architect", 40)):
            write_jsonl(subagents / f"agent-{agent_id}.jsonl", [reply("model-b", agent_id, 7, out)])
            (subagents / f"agent-{agent_id}.meta.json").write_text(json.dumps({"agentType": agent}))
        # A truncated last line (session still being written) must be skipped, not crash.
        with open(subagents / "agent-a3.jsonl", "a", encoding="utf-8") as fh:
            fh.write('{"type": "assist')

    def tearDown(self):
        self.tmp.cleanup()

    def talk(self, *messages, project=None):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.home),
                   CLAUDE_PROJECT_DIR=str(project or self.project))
        stdin = "".join(json.dumps(m) + "\n" for m in messages)
        proc = subprocess.run([sys.executable, str(SERVER)], input=stdin, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=30)
        replies = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        return {r["id"]: r for r in replies}, replies

    def call(self, name, arguments=None, **kw):
        by_id, _ = self.talk(INIT, INITIALIZED,
                             {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": name, "arguments": arguments or {}}}, **kw)
        result = by_id[1]["result"]
        return result["content"][0]["text"], result.get("isError", False)

    def test_handshake_and_notification_gets_no_reply(self):
        by_id, replies = self.talk(INIT, INITIALIZED)
        self.assertEqual(len(replies), 1)  # initialize answered, notification not
        result = by_id[0]["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "devorg-token-tracker")

    def test_unknown_protocol_version_gets_servers_own(self):
        odd = dict(INIT, params=dict(INIT["params"], protocolVersion="1999-01-01"))
        by_id, _ = self.talk(odd)
        self.assertRegex(by_id[0]["result"]["protocolVersion"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertNotEqual(by_id[0]["result"]["protocolVersion"], "1999-01-01")

    def test_tools_list(self):
        by_id, _ = self.talk(INIT, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = {t["name"]: t for t in by_id[1]["result"]["tools"]}
        self.assertEqual(set(tools), {"list_sessions", "session_usage", "usage_by_agent"})
        for tool in tools.values():
            self.assertTrue(tool["description"])
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_session_usage_counts_each_message_once_and_names_agents(self):
        text, is_error = self.call("session_usage")
        self.assertFalse(is_error)
        # main: m1 (100+50+1000) + m2 (10+5+2000) = 3165, not 4315 (m1 counted twice)
        self.assertIn("| main session | 1 | 110 | 1.0k | 2.0k | 55 | 3.2k |", text)
        self.assertIn("| devorg:developer-2 | 2 | 14 | 0 | 0 | 500 | 514 |", text)
        self.assertIn("| devorg:system-architect | 1 | 7 | 0 | 0 | 40 | 47 |", text)
        self.assertIn("| **TOTAL** | 4 |", text)
        self.assertIn("model-a", text)
        self.assertIn("model-b", text)

    def test_list_sessions(self):
        text, is_error = self.call("list_sessions")
        self.assertFalse(is_error)
        self.assertIn("| s1 |", text)
        self.assertIn("| 3 |", text)  # three subagents

    def test_usage_by_agent(self):
        text, is_error = self.call("usage_by_agent", {"days": 30})
        self.assertFalse(is_error)
        self.assertIn("devorg:developer-2", text)

    def test_bad_input_is_a_tool_error_not_a_crash(self):
        for name, args in (("session_usage", {"session_id": "nope"}),
                           ("session_usage", {"session_id": "../../secrets"}),
                           ("list_sessions", {"limit": 0}),
                           ("usage_by_agent", {"days": "lots"})):
            with self.subTest(name=name, args=args):
                _, is_error = self.call(name, args)
                self.assertTrue(is_error)

    def test_project_without_transcripts(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        text, is_error = self.call("session_usage", project=other)
        self.assertTrue(is_error)
        self.assertIn("No Claude Code transcripts", text)

    def test_protocol_errors(self):
        by_id, _ = self.talk(INIT,
                             {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
                             {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                              "params": {"name": "delete_everything"}},
                             {"jsonrpc": "2.0", "id": 3, "method": "ping"})
        self.assertEqual(by_id[1]["error"]["code"], -32601)  # method not found
        self.assertEqual(by_id[2]["error"]["code"], -32602)  # invalid params (unknown tool)
        self.assertEqual(by_id[3]["result"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
