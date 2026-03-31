#!/bin/bash
# Toggle broot file explorer sidebar in CMux.
# Opens a vertical split (left) with broot, or closes the existing broot pane.
# CMux version — uses `cmux new-split` / `cmux send-key` instead of iTerm2 AppleScript.
# Usage: bash ~/.claude/hooks/broot-pane-toggle-cmux.sh

# Only run inside CMux
if [[ -z "$CMUX_WORKSPACE_ID" ]]; then
    echo "Not running in CMux" >&2
    exit 1
fi

MARKER="$HOME/.claude/broot-pane-id"

# Check if broot pane is already open
if [[ -f "$MARKER" ]]; then
    BROOT_PANE=$(cat "$MARKER")
    # Verify the surface still exists (list-panes shows pane refs, tree shows surface refs)
    if cmux tree 2>/dev/null | grep -q "$BROOT_PANE"; then
        # Pane exists — close it cleanly
        cmux close-surface --surface "$BROOT_PANE" 2>/dev/null
        rm -f "$MARKER"
        exit 0
    else
        # Stale marker — pane is gone
        rm -f "$MARKER"
    fi
fi

# broot not running — create a left split and launch broot in it
CWD=$(pwd)
SESSION_ID="${CLAUDE_SESSION_ID:-default}"

# Create split (shell spawns), then send broot command
# Using send+exec instead of respawn-pane to keep surface ID stable
RESULT=$(cmux new-split left 2>&1)

# Parse surface ID from "OK surface:N workspace:N"
PANE_ID=$(echo "$RESULT" | grep -oE 'surface:[0-9a-zA-Z-]+' | head -1)

if [[ -n "$PANE_ID" ]]; then
    echo "$PANE_ID" > "$MARKER"
    sleep 0.5
    cmux send --surface "$PANE_ID" "CLAUDE_SESSION_ID='$SESSION_ID' exec broot '$CWD'" 2>/dev/null
    cmux send-key --surface "$PANE_ID" Enter 2>/dev/null
fi

exit 0
