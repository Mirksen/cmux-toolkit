#!/bin/bash
# UserPromptSubmit hook: reset changes view for new prompt cycle.
# Clears the changes log and navigates the browser tab to an empty state.
# Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
[[ -z "$SESSION_ID" ]] && exit 0

# Append current changes to cumulative session log before clearing
PROMPT_LOG="$VIEW_CHANGES_DIR/${SESSION_ID}.jsonl"
SESSION_LOG="$VIEW_CHANGES_DIR/${SESSION_ID}-all.jsonl"
if [[ -s "$PROMPT_LOG" ]]; then
    cat "$PROMPT_LOG" >> "$SESSION_LOG"
fi
rm -f "$PROMPT_LOG" 2>/dev/null

# Keep the browser showing the last changes — it will update when new edits happen

exit 0
