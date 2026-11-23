#!/bin/sh
# Launcher for DevOrg hooks. Usage: run-hook.sh <guard-edit|guard-bash|guard-read|gate>
#
# 1. If DevOrg isn't set up in this project (.devorg/config.json missing), do nothing:
#    the plugin must not affect projects that don't use it.
# 2. Find a working Python 3.8+ (python3 on macOS/Linux, python or py on Windows).
# 3. If none is found in a DevOrg project, fail CLOSED for guards (exit 2 blocks the
#    tool call) so a missing interpreter can't silently switch the safety rules off.

PROJECT="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$PROJECT/.devorg/config.json" ] || exit 0

ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}"

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 &&
     "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' </dev/null >/dev/null 2>&1; then
    exec "$py" "$ROOT/scripts/devorg_hooks.py" "$@"
  fi
done

echo "DevOrg: Python 3.8+ was not found, so DevOrg cannot check this action. Install Python 3 and make sure 'python3' or 'python' is on PATH." >&2
[ "$1" = "gate" ] && exit 1
exit 2
