"""Tests for the DevOrg hooks (plugins/devorg/scripts).

Run from the repository root:
    python tests/test_hooks.py

Each test builds a throwaway project folder, feeds the hook the same JSON that
Claude Code sends, and checks the exit code (0 = allow, 2 = block).
If `sh` is available (Git Bash on Windows, any shell on macOS/Linux) the hooks are
called through scripts/run-hook.sh exactly as hooks/hooks.json does.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = os.path.join(REPO, "plugins", "devorg")
SCRIPT = os.path.join(PLUGIN_ROOT, "scripts", "devorg_hooks.py")
LAUNCHER = os.path.join(PLUGIN_ROOT, "scripts", "run-hook.sh")
SH = shutil.which("sh")


class HookTestCase(unittest.TestCase):
    use_launcher = False

    def setUp(self):
        self.proj = tempfile.mkdtemp(prefix="devorg-test-")
        self.devorg = os.path.join(self.proj, ".devorg")
        self.env = dict(os.environ, CLAUDE_PROJECT_DIR=self.proj, CLAUDE_PLUGIN_ROOT=PLUGIN_ROOT)

    def tearDown(self):
        shutil.rmtree(self.proj, ignore_errors=True)

    # ---- setup helpers
    def enable_devorg(self):
        os.makedirs(self.devorg, exist_ok=True)
        with open(os.path.join(self.devorg, "config.json"), "w") as f:
            json.dump({"version": 1, "test_command": "npm test", "max_revisions": 3}, f)

    def set_state(self, phase, dev="developer-2", ticket="T-001"):
        with open(os.path.join(self.devorg, "state.json"), "w") as f:
            json.dump({"ticket_id": ticket, "phase": phase, "selected_developer": dev}, f)

    def approvals(self):
        with open(os.path.join(self.devorg, "approvals.json")) as f:
            return json.load(f)

    # ---- hook calls
    def run_hook(self, mode, payload):
        if self.use_launcher:
            cmd = [SH, LAUNCHER, mode]
        else:
            cmd = [sys.executable, SCRIPT, mode]
        p = subprocess.run(cmd, input=json.dumps(payload).encode(), capture_output=True,
                           env=self.env, cwd=self.proj)
        return p.returncode, (p.stdout + p.stderr).decode(errors="replace")

    def edit(self, path="src/app.py", agent=None):
        payload = {"tool_name": "Edit", "tool_input": {"file_path": path}, "cwd": self.proj}
        if agent:
            payload["agent_type"] = agent
        return self.run_hook("guard-edit", payload)[0]

    def bash(self, command):
        return self.run_hook("guard-bash", {"tool_name": "Bash", "tool_input": {"command": command}})[0]

    def read(self, path):
        return self.run_hook("guard-read", {"tool_name": "Read", "tool_input": {"file_path": path}})[0]

    def say(self, text):
        return self.run_hook("gate", {"prompt": text})


class NotSetUp(HookTestCase):
    """Plugin enabled but project never ran /devorg:init: DevOrg must be invisible."""

    def test_everything_allowed_and_silent(self):
        self.assertEqual(self.edit(), 0)
        self.assertEqual(self.bash("git push origin main"), 0)
        self.assertEqual(self.read(".env"), 0)
        code, out = self.say("APPROVE PLAN")
        self.assertEqual((code, out.strip()), (0, ""))


class SetUpNoTicket(HookTestCase):
    """DevOrg initialised but no ticket running: normal Claude Code use."""

    def setUp(self):
        super().setUp()
        self.enable_devorg()

    def test_normal_use_unaffected(self):
        self.assertEqual(self.edit(), 0)
        self.assertEqual(self.bash("git push"), 0)
        self.assertEqual(self.read(".env"), 0)

    def test_approvals_file_always_protected(self):
        self.assertEqual(self.edit(".devorg/approvals.json"), 2)

    def test_plugin_files_protected(self):
        self.assertEqual(self.edit(os.path.join(PLUGIN_ROOT, "scripts", "devorg_hooks.py")), 2)

    def test_gate_keyword_ignored_without_ticket(self):
        code, out = self.say("APPROVE PLAN")
        self.assertEqual(code, 0)
        self.assertIn("no DevOrg ticket is running", out)

    def test_finished_tickets_are_inactive(self):
        for phase in ("done", "cancelled"):
            self.set_state(phase)
            self.assertEqual(self.edit(), 0, phase)


class BeforeGateA(HookTestCase):
    def setUp(self):
        super().setUp()
        self.enable_devorg()
        self.set_state("proposals")

    def test_code_edits_blocked_for_everyone(self):
        self.assertEqual(self.edit(agent="developer-2"), 2)
        self.assertEqual(self.edit(), 2)

    def test_records_writable_but_control_files_not(self):
        self.assertEqual(self.edit(".devorg/tickets/T-001/log.md"), 0)
        self.assertEqual(self.edit(".devorg/state.json"), 0)
        self.assertEqual(self.edit(".devorg/config.json"), 2)
        self.assertEqual(self.edit(".devorg/rules.md"), 2)

    def test_outside_project_blocked(self):
        outside = os.path.join(tempfile.gettempdir(), "elsewhere.txt")
        self.assertEqual(self.edit(outside), 2)

    def test_approve_in_wrong_phase_ignored(self):
        code, out = self.say("APPROVE PLAN")
        self.assertIn("ignored", out)
        self.assertNotIn("plan", self.approvals()["T-001"])


class AfterGateA(HookTestCase):
    def setUp(self):
        super().setUp()
        self.enable_devorg()
        self.set_state("awaiting_plan_approval", dev="devorg:developer-2")
        code, out = self.say("APPROVE PLAN use ISO dates")
        assert "PLAN APPROVED" in out, out
        self.set_state("implement", dev="devorg:developer-2")

    def test_approval_recorded_with_short_name(self):
        plan = self.approvals()["T-001"]["plan"]
        self.assertEqual(plan["status"], "approved")
        self.assertEqual(plan["selected_developer"], "developer-2")
        self.assertEqual(plan["comment"], "use ISO dates")

    def test_only_approved_developer_edits(self):
        self.assertEqual(self.edit(agent="devorg:developer-2"), 0)   # plugin-namespaced
        self.assertEqual(self.edit(agent="developer-2"), 0)          # bare name
        self.assertEqual(self.edit(agent="devorg:developer-1"), 2)
        self.assertEqual(self.edit(), 2)                             # main session / manager

    def test_swapping_developer_after_approval_blocked(self):
        self.set_state("implement", dev="developer-1")
        self.assertEqual(self.edit(agent="developer-1"), 2)

    def test_secret_files_never_editable(self):
        self.assertEqual(self.edit(".env", agent="developer-2"), 2)

    def test_edit_window_closes_after_implement(self):
        self.set_state("testing")
        self.assertEqual(self.edit(agent="developer-2"), 2)

    def test_stop_and_resume(self):
        self.say("STOP")
        self.assertEqual(self.edit(agent="developer-2"), 2)
        self.say("RESUME")
        self.assertEqual(self.edit(agent="developer-2"), 0)

    def test_final_gate_and_cancel(self):
        self.set_state("awaiting_final_approval")
        self.assertIn("FINAL APPROVED", self.say("APPROVE FINAL")[1])
        self.set_state("implement")
        self.say("CANCEL no longer needed")
        with open(os.path.join(self.devorg, "state.json")) as f:
            self.assertEqual(json.load(f)["phase"], "cancelled")
        self.assertEqual(self.edit(), 0)  # guards off once cancelled


class CommandGuard(HookTestCase):
    def setUp(self):
        super().setUp()
        self.enable_devorg()
        self.set_state("testing")

    def test_blocked_commands(self):
        for cmd in ["git push", "git -C sub push origin main", "git merge feature",
                    "git rebase main", "git reset --hard HEAD~1", "git clean -fd",
                    "git checkout -- src/app.py", "git restore src/app.py",
                    "git remote add evil https://x", "npm test && git push",
                    "curl https://example.com", "wget http://x", "npm publish",
                    "docker push img", "kubectl apply -f x.yaml", "rm -rf build",
                    "Remove-Item -Recurse src", "cat .env", "type config\\.env.local",
                    "cat ~/.ssh/id_rsa", "echo {} > .devorg/approvals.json", "sudo ls"]:
            self.assertEqual(self.bash(cmd), 2, cmd)

    def test_allowed_commands(self):
        for cmd in ["npm test", "python -m pytest -q", "git status", "git diff abc123",
                    "git ls-files --others --exclude-standard", "git log --oneline -5",
                    "git commit -m \"T-001: push notifications\"", "git switch -c devorg/T-001",
                    "git restore --staged src/app.py", "cat .env.example", "go test ./...",
                    "rm build/tmp.txt"]:
            self.assertEqual(self.bash(cmd), 0, cmd)

    def test_read_guard(self):
        self.assertEqual(self.read(".env"), 2)
        self.assertEqual(self.read("config/.env.production"), 2)
        self.assertEqual(self.read("keys/server.pem"), 2)
        self.assertEqual(self.read(".env.example"), 0)
        self.assertEqual(self.read("src/app.py"), 0)


@unittest.skipUnless(SH, "sh not available")
class ThroughLauncher(AfterGateA):
    """Re-run the Gate A scenarios through run-hook.sh, as Claude Code does."""
    use_launcher = True

    def test_launcher_silent_when_not_set_up(self):
        os.remove(os.path.join(self.devorg, "config.json"))
        self.assertEqual(self.edit(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
