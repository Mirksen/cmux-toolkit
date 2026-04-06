#!/bin/bash
# SessionStart hook: export CMUX_SESSION_ID to the shell environment.
# This makes the session ID available to commands like `changes`.

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
[[ -z "$SESSION_ID" ]] && exit 0

# Persist session ID for shell commands (! changes, etc.)
[[ -n "$CLAUDE_ENV_FILE" ]] && echo "export CMUX_SESSION_ID='$SESSION_ID'" >> "$CLAUDE_ENV_FILE"

# Clean up stale session files older than 24h
find "$VIEW_CHANGES_DIR" -name '*.jsonl' -mtime +1 -delete 2>/dev/null
find "$VIEW_SURFACES_DIR" -name '*.txt' -mtime +1 -delete 2>/dev/null
find "$VIM_PANES_DIR" -name '*.ref' -mtime +1 -delete 2>/dev/null

exit 0
