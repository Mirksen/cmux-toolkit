#!/usr/bin/env python3
"""Claude Code PostToolUse hook: send opened/edited file paths to Vim.

Appends the file path to a session-specific signal file so the matching
Vim instance picks up ALL files touched in a prompting round.
"""
import json, sys, os, fcntl

data = json.load(sys.stdin)
session_id = data.get("session_id", "default")
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if not file_path or not os.path.isfile(file_path):
    sys.exit(0)

signal_file = os.path.expanduser(f"~/.vim/claude-open-file-{session_id}")
os.makedirs(os.path.dirname(signal_file), exist_ok=True)

# Append with file lock to avoid lost writes from concurrent hooks
with open(signal_file, "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.write(file_path + "\n")
