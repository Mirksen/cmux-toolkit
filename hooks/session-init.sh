#!/bin/bash
# SessionStart hook: initialize session state and clean up stale files.

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
[[ -z "$SESSION_ID" ]] && exit 0

# Clean up stale session files older than 24h
find "$VIEW_CHANGES_DIR" -name '*.jsonl' -mtime +1 -delete 2>/dev/null
find "$VIEW_SURFACES_DIR" -name '*.txt' -mtime +1 -delete 2>/dev/null
find "$VIM_PANES_DIR" -name '*.ref' -mtime +1 -delete 2>/dev/null

exit 0
