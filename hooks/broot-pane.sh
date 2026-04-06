#!/bin/bash
# broot file explorer sidebar for CMux.
# Usage:
#   bash broot-pane.sh          — toggle (keybind, e.g. Opt+E)
#   bash broot-pane.sh --open   — open only, reads hook JSON from stdin (SessionStart)

[[ -z "$CMUX_WORKSPACE_ID" ]] && exit 0

MODE="toggle"
[[ "$1" == "--open" ]] && MODE="open"

MARKER="$HOME/.claude/broot-pane-id"

# --- Toggle: close if already open ---
if [[ "$MODE" == "toggle" && -f "$MARKER" ]]; then
    BROOT_PANE=$(cat "$MARKER")
    if cmux tree 2>/dev/null | grep -q "$BROOT_PANE"; then
        cmux close-surface --surface "$BROOT_PANE" 2>/dev/null
        rm -f "$MARKER"
        exit 0
    fi
    rm -f "$MARKER"  # stale marker
fi

# --- Open broot in a left split ---
if [[ "$MODE" == "open" ]]; then
    INPUT=$(cat)
    eval "$(echo "$INPUT" | jq -r '@sh "SESSION_ID=\(.session_id // "") CWD=\(.cwd // "")"')"
    [[ -z "$SESSION_ID" ]] && exit 0
    [[ -z "$CWD" ]] && CWD=$(pwd)
    sleep 0.5  # let Vim pane settle (vim-pane-open runs first)
else
    CWD=$(pwd)
    SESSION_ID="${CLAUDE_SESSION_ID:-default}"
fi

# Get Claude's pane ref for refocus later
CLAUDE_PANE=$(cmux identify 2>/dev/null | jq -r '.caller.pane_ref' 2>/dev/null)

# Create left split
RESULT=$(cmux new-split left --surface "${CMUX_SURFACE_ID:-}" 2>&1)
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
