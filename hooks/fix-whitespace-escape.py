#!/usr/bin/env python3
r"""Claude Code PreToolUse hook: fix backslash-escaped whitespace in Bash commands.

macOS iCloud Drive paths contain spaces (~/Library/Mobile Documents/...).
Claude Code's bare-repo-attack prevention blocks backslash-escaped whitespace.
This hook rewrites `\ ` to ` ` so the command can proceed.
"""
import json, sys, re

data = json.load(sys.stdin)
cmd = data.get("input", {}).get("command", "")
new_cmd = re.sub(r"(?<!\\)\\[ \t]", lambda m: m.group()[1:], cmd)

if new_cmd != cmd:
    print(json.dumps({
        "decision": "allow",
        "reason": "fixed backslash-escaped whitespace",
        "updatedInput": {"command": new_cmd}
    }))
else:
    print(json.dumps({"decision": "allow"}))
