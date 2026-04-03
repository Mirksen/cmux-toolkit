#!/usr/bin/env python3
"""Claude Code PostToolUse hook: render edited/written files in cmux browser tab.

On Edit/Write:
1. Writes new_string to a diff temp file (for Edit)
2. Calls viewtab to render the file with diff highlighting
3. Tracks the created surface ID for later cleanup (prompt reset / session end)
"""
import json, sys, os, subprocess, fcntl, re

data = json.load(sys.stdin)
session_id = data.get("session_id", "default")
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if not file_path or not os.path.isfile(file_path):
    sys.exit(0)

# --- Diff file for Edit tool ---
diff_file = ""
if tool_name == "Edit":
    new_string = tool_input.get("new_string", "")
    if new_string:
        diff_file = f"/tmp/view-diff-{session_id}.txt"
        with open(diff_file, "w") as f:
            f.write(new_string)

# --- Call viewtab ---
env = os.environ.copy()
if diff_file:
    env["VIEW_DIFF_FILE"] = diff_file

try:
    result = subprocess.run(
        ["viewtab", file_path],
        env=env, capture_output=True, text=True, timeout=15
    )
    output = result.stdout.strip()
except Exception:
    sys.exit(0)

# --- Track surface ID for cleanup ---
# Output format: "OK surface:123 pane:45 workspace:1\nOpened: foo.md"
surface_match = re.search(r'surface:(\d+)', output)
if surface_match:
    surface_ref = f"surface:{surface_match.group(1)}"
    tracking_dir = os.path.expanduser("~/.claude/view-surfaces")
    os.makedirs(tracking_dir, exist_ok=True)
    tracking_file = os.path.join(tracking_dir, f"{session_id}.txt")

    with open(tracking_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(surface_ref + "\n")

# Clean up diff file
if diff_file and os.path.exists(diff_file):
    os.unlink(diff_file)
