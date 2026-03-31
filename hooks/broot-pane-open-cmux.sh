#!/bin/bash
# Claude Code SessionStart hook: open broot file explorer as a left vertical split.
# CMux version — uses `cmux new-split` instead of iTerm2 AppleScript.
# Runs AFTER vim-pane-open.sh — the Vim pane must exist first.

[[ -z "$CMUX_WORKSPACE_ID" ]] && exit 0

INPUT=$(cat)

# Extract session_id and cwd from hook JSON
eval "$(echo "$INPUT" | jq -r '@sh "SESSION_ID=\(.session_id // "") CWD=\(.cwd // "")"')"

[[ -z "$SESSION_ID" ]] && exit 0
[[ -z "$CWD" ]] && CWD=$(pwd)

# Brief delay to let Vim pane settle (vim-pane-open runs first)
sleep 0.5

MARKER="$HOME/.claude/broot-pane-id"

# Get Claude's pane ref for refocus later
CLAUDE_PANE=$(cmux identify 2>/dev/null | jq -r '.caller.pane_ref' 2>/dev/null)

# Create left split, then send broot command
# Using send+exec instead of respawn-pane to keep surface ID stable
RESULT=$(cmux new-split left --surface "$CMUX_SURFACE_ID" 2>&1)

# Parse surface ID from "OK surface:N workspace:N"
BROOT_SURFACE=$(echo "$RESULT" | grep -oE 'surface:[0-9a-zA-Z-]+' | head -1)

if [[ -n "$BROOT_SURFACE" ]]; then
    echo "$BROOT_SURFACE" > "$MARKER"
    sleep 0.5
    cmux send --surface "$BROOT_SURFACE" "CLAUDE_SESSION_ID='$SESSION_ID' exec broot '$CWD'" 2>/dev/null
    cmux send-key --surface "$BROOT_SURFACE" Enter 2>/dev/null
fi

# Refocus Claude pane
[[ -n "$CLAUDE_PANE" ]] && cmux focus-pane "$CLAUDE_PANE" 2>/dev/null

exit 0
