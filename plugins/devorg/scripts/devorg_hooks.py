"""DevOrg enforcement hooks — works in any project.

The plugin's hooks fire in every project where the plugin is enabled, so every
check below starts with: "is DevOrg set up here (.devorg/config.json exists)?"
If not, the hook does nothing. Rules are enforced only while a ticket is active
(state.json exists and its phase is not done/cancelled), so normal Claude Code
use in the same project is never affected.

Modes (called by hooks/hooks.json through scripts/run-hook.sh):

  guard-edit   PreToolUse  Edit|Write|MultiEdit|NotebookEdit
               During a ticket, project files may only change when:
                 - the human typed APPROVE PLAN (recorded in approvals.json),
                 - the phase is "implement",
                 - the ticket is not stopped,
                 - the edit comes from the developer the human approved.
               .devorg/ records stay writable; approvals.json, config.json and
               rules.md are never writable by agents.

  guard-bash   PreToolUse  Bash|PowerShell
               During a ticket: no push/merge/rebase/destructive git, no
               publishing/deploying, no network tools, no reading secrets, no
               touching approvals.json.

  guard-read   PreToolUse  Read
               During a ticket: no reading .env files, private keys, credentials.

  gate         UserPromptSubmit
               Records the human's typed decisions in .devorg/approvals.json:
               APPROVE PLAN / REJECT PLAN / APPROVE FINAL / REJECT FINAL /
               STOP / RESUME / CANCEL (uppercase, at the start of the message).

Exit code 2 = block the tool call (stderr is shown to Claude). Standard library only.
"""

import json
import os
import re
import shlex
import sys
from datetime import datetime

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
DEVORG_DIR = os.path.join(PROJECT_DIR, ".devorg")
CONFIG_FILE = os.path.join(DEVORG_DIR, "config.json")
RULES_FILE = os.path.join(DEVORG_DIR, "rules.md")
STATE_FILE = os.path.join(DEVORG_DIR, "state.json")
APPROVALS_FILE = os.path.join(DEVORG_DIR, "approvals.json")

INACTIVE_PHASES = {"done", "cancelled"}

GATE_PATTERN = re.compile(
    r"^\s*(APPROVE PLAN|REJECT PLAN|APPROVE FINAL|REJECT FINAL|STOP|RESUME|CANCEL)\b(.*)$",
    re.DOTALL)

# --------------------------------------------------------------------------- helpers


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_stdin_json():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else {}


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def norm(path):
    return os.path.normcase(os.path.realpath(path))


def same(a, b):
    return norm(a) == norm(b)


def is_inside(path, folder):
    try:
        return os.path.commonpath([norm(path), norm(folder)]) == norm(folder)
    except ValueError:  # different drives on Windows
        return False


def short_agent(name):
    """'devorg:developer-2' -> 'developer-2' (plugin agents are namespaced)."""
    return name.split(":")[-1] if name else None


def devorg_enabled():
    return os.path.isfile(CONFIG_FILE)


def active_state():
    """The state of the running ticket, or None when no ticket is running."""
    state = load_json(STATE_FILE, None)
    if not state or not state.get("ticket_id"):
        return None
    if state.get("phase") in INACTIVE_PHASES:
        return None
    return state


def ticket_record(state):
    return load_json(APPROVALS_FILE, {}).get(state["ticket_id"], {})


def allow():
    sys.exit(0)


def block(message):
    print(f"DevOrg guard: {message}", file=sys.stderr)
    sys.exit(2)


def resolve(path, cwd):
    if not os.path.isabs(path):
        path = os.path.join(cwd or PROJECT_DIR, path)
    return path


# --------------------------------------------------------------------------- secrets

SAFE_ENV_SUFFIXES = (".example", ".sample", ".template", ".dist")
SECRET_NAME_PATTERNS = [
    re.compile(r"^\.env(\..+)?$"),
    re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$"),
    re.compile(r".*\.(pem|key|p12|pfx|keystore|jks)$"),
    re.compile(r"^(credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)$"),
]
SECRET_DIRS = {"secrets", ".ssh", ".aws", ".gnupg"}


def is_secret_path(path):
    parts = re.split(r"[\\/]+", path)
    name = parts[-1].lower()
    if name.startswith(".env") and name.endswith(SAFE_ENV_SUFFIXES):
        return False
    if any(p.lower() in SECRET_DIRS for p in parts[:-1]):
        return True
    return any(p.match(name) for p in SECRET_NAME_PATTERNS)


# --------------------------------------------------------------------------- guard-edit


def guard_edit():
    if not devorg_enabled():
        allow()
    data = read_stdin_json()
    tool_input = data.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        allow()
    target = resolve(target, data.get("cwd"))

    if same(target, APPROVALS_FILE):
        block("approvals.json is written only by the human-approval hook. "
              "Ask the human to type the gate keyword (e.g. APPROVE PLAN).")
    if is_inside(target, PLUGIN_ROOT):
        block("the DevOrg plugin's own files cannot be modified by agents.")

    state = active_state()
    if state is None:
        allow()  # no ticket running: normal Claude Code use

    ticket = state["ticket_id"]
    if same(target, CONFIG_FILE) or same(target, RULES_FILE):
        block(f"{os.path.basename(target)} cannot change while ticket {ticket} is running.")
    if is_inside(target, DEVORG_DIR):
        allow()  # records and state
    if not is_inside(target, PROJECT_DIR):
        block(f"{target} is outside the project. DevOrg agents only change this project.")
    if is_secret_path(target):
        block("secret/credential files cannot be edited by DevOrg agents.")

    record = ticket_record(state)
    if record.get("stopped"):
        block(f"ticket {ticket} was stopped by the human. Nothing may change until they type RESUME.")
    plan = record.get("plan") or {}
    if plan.get("status") != "approved":
        block(f"Gate A not passed for {ticket}: the human has not typed APPROVE PLAN. "
              "No code changes before plan approval.")
    if state.get("phase") != "implement":
        block(f"ticket {ticket} is in phase '{state.get('phase')}', not 'implement'. "
              "Only the selected developer may edit, during step 7.")
    approved = short_agent(plan.get("selected_developer"))
    agent = short_agent(data.get("agent_type"))
    if agent != approved:
        who = agent or "the main session (Engineering Manager)"
        block(f"only {approved} (approved by the human at Gate A) may edit project files; "
              f"this edit came from {who}.")
    allow()


# --------------------------------------------------------------------------- guard-bash

SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
GIT_GLOBAL_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
NETWORK_TOOLS = {"curl", "wget", "invoke-webrequest", "iwr", "invoke-restmethod", "irm",
                 "scp", "sftp", "ftp", "nc", "ncat", "telnet"}
DEPLOY_TOOLS = {"kubectl", "helm", "eksctl"}
PUBLISH_PAIRS = {("npm", "publish"), ("yarn", "publish"), ("pnpm", "publish"),
                 ("cargo", "publish"), ("twine", "upload"), ("docker", "push"),
                 ("podman", "push"), ("terraform", "apply"), ("terraform", "destroy"),
                 ("gem", "push"), ("dotnet", "nuget"), ("mvn", "deploy"),
                 ("gh", "release"), ("vercel", "--prod"), ("firebase", "deploy")}


def tokens(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def git_problem(args):
    """args = tokens after 'git'. Return a reason string if the git command is not allowed."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in GIT_GLOBAL_OPTS_WITH_VALUE:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    if sub in {"push", "merge", "rebase", "pull", "cherry-pick", "filter-branch"}:
        return f"git {sub} is not allowed in DevOrg (no pushes or merges; history stays local and linear)"
    if sub == "reset" and "--hard" in rest:
        return "git reset --hard would discard work"
    if sub == "clean" and any(r.startswith("-") and "f" in r for r in rest):
        return "git clean -f would delete files"
    if sub == "checkout" and ("--" in rest or "." in rest):
        return "git checkout -- / . would discard work"
    if sub == "restore" and "--staged" not in rest:
        return "git restore would discard work"
    if sub == "remote" and rest[:1] and rest[0] in {"add", "set-url"}:
        return "changing git remotes is not allowed"
    if sub == "branch" and any(r in {"-D", "-d", "--delete"} for r in rest):
        return "deleting branches is not allowed"
    return None


def command_problem(command):
    lowered = command.lower()
    if "approvals.json" in lowered:
        return "approvals.json is written only by the human-approval hook"
    for segment in SEGMENT_SPLIT.split(command):
        toks = tokens(segment.strip())
        if not toks:
            continue
        # skip leading env assignments like FOO=1 cmd
        while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
            toks = toks[1:]
        if not toks:
            continue
        exe = os.path.basename(toks[0]).lower()
        if exe.endswith(".exe"):
            exe = exe[:-4]
        if exe == "sudo":
            return "sudo is not allowed"
        if exe == "git":
            reason = git_problem(toks[1:])
            if reason:
                return reason
        if exe in NETWORK_TOOLS:
            return f"network tool '{exe}' is not allowed during a DevOrg ticket"
        if exe in DEPLOY_TOOLS:
            return f"'{exe}' (deployment) is not allowed during a DevOrg ticket"
        if len(toks) > 1 and (exe, toks[1].lower()) in PUBLISH_PAIRS:
            return f"'{exe} {toks[1]}' (publishing/deploying) is not allowed"
        if exe in {"rm", "remove-item", "del", "rmdir", "rd"} and any(
                t.lower() in {"-recurse", "/s"} or (t.startswith("-") and not t.startswith("--")
                                                    and re.search(r"[rRf]", t)) for t in toks[1:]):
            return "recursive/forced deletion is not allowed during a DevOrg ticket"
        # check both the shell-parsed tokens and the raw words: shlex eats Windows
        # backslashes ("config\.env" -> "config.env"), the raw words keep them
        for t in toks[1:] + segment.split()[1:]:
            t = t.strip("'\"")
            if t and not t.startswith("-") and is_secret_path(t):
                return f"'{t}' looks like a secret/credential file"
    return None


def guard_bash():
    if not devorg_enabled():
        allow()
    data = read_stdin_json()
    if active_state() is None:
        allow()
    command = (data.get("tool_input") or {}).get("command") or ""
    reason = command_problem(command)
    if reason:
        block(f"{reason}. If the human needs this, they can run it themselves.")
    allow()


# --------------------------------------------------------------------------- guard-read


def guard_read():
    if not devorg_enabled():
        allow()
    data = read_stdin_json()
    if active_state() is None:
        allow()
    target = (data.get("tool_input") or {}).get("file_path") or ""
    if target and is_secret_path(target):
        block("secret/credential files (.env, keys, credentials) are never read by DevOrg agents.")
    allow()


# --------------------------------------------------------------------------- gate


def gate():
    if not devorg_enabled():
        allow()  # DevOrg not set up in this project: stay silent
    data = read_stdin_json()
    match = GATE_PATTERN.match(data.get("prompt") or "")
    if not match:
        allow()

    keyword, comment = match.group(1), match.group(2).strip()
    state = active_state()
    if state is None:
        print(f"[DevOrg gate] '{keyword}' ignored: no DevOrg ticket is running.")
        allow()

    ticket, phase = state["ticket_id"], state.get("phase")
    approvals = load_json(APPROVALS_FILE, {})
    record = approvals.setdefault(ticket, {})
    entry = {"at": now(), "keyword": keyword, "comment": comment, "phase": phase}

    def finish(message, recorded=True):
        entry["recorded"] = recorded
        record.setdefault("log", []).append(entry)
        save_json(APPROVALS_FILE, approvals)
        print(f"[DevOrg gate] {message}")
        allow()

    if keyword == "STOP":
        record["stopped"] = {"at": entry["at"], "comment": comment}
        finish(f"STOP recorded for {ticket}. Project edits are now blocked. "
               "Engineering Manager: set phase to 'stopped', summarise, and wait for RESUME or CANCEL.")
    if keyword == "RESUME":
        if not record.pop("stopped", None):
            finish(f"RESUME ignored: {ticket} is not stopped.", recorded=False)
        finish(f"RESUME recorded for {ticket}. Engineering Manager: re-read state.json and continue.")
    if keyword == "CANCEL":
        record["cancelled"] = {"at": entry["at"], "comment": comment}
        state["phase"] = "cancelled"
        state["updated_at"] = entry["at"]
        save_json(STATE_FILE, state)
        finish(f"CANCEL recorded: ticket {ticket} is closed and DevOrg's guards are off. "
               "Engineering Manager: log it and summarise what was (not) changed.")

    gate_name = "plan" if keyword.endswith("PLAN") else "final"
    expected = "awaiting_plan_approval" if gate_name == "plan" else "awaiting_final_approval"
    if phase != expected:
        finish(f"'{keyword}' ignored: {ticket} is in phase '{phase}', not '{expected}'.",
               recorded=False)

    status = "approved" if keyword.startswith("APPROVE") else "rejected"
    decision = {"status": status, "at": entry["at"], "comment": comment}
    if gate_name == "plan":
        decision["selected_developer"] = short_agent(state.get("selected_developer"))
        if status == "approved":
            record.pop("final", None)  # a fresh plan approval resets any earlier final decision
    record[gate_name] = decision

    extra = (f" (implementer: {decision['selected_developer']})"
             if gate_name == "plan" and status == "approved" else "")
    finish(f"{gate_name.upper()} {status.upper()}{extra} for {ticket} by the human at {entry['at']}."
           + (f" Comment: {comment}" if comment else ""))


MODES = {"guard-edit": guard_edit, "guard-bash": guard_bash,
         "guard-read": guard_read, "gate": gate}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in MODES:
        print(f"usage: devorg_hooks.py {'|'.join(MODES)}", file=sys.stderr)
        sys.exit(1)
    MODES[mode]()
