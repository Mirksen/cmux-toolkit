#!/usr/bin/env python3
"""PostToolUse hook: send opened/edited file paths to Vim.

Appends the file path to a session-specific signal file so the matching
Vim instance picks up ALL files touched in a prompting round.

Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.
"""
import json, sys, os, fcntl

# Import shared config (resolve through symlinks)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'lib'))
from common import signal_file_for

data = json.load(sys.stdin)
session_id = data.get("session_id", "default")
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if not file_path or not os.path.isfile(file_path):
    sys.exit(0)

signal_file = signal_file_for(session_id)
os.makedirs(os.path.dirname(signal_file), exist_ok=True)

# Append with file lock to avoid lost writes from concurrent hooks
with open(signal_file, "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.write(file_path + "\n")
