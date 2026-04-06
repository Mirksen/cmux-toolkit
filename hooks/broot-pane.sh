#!/bin/bash
# broot file explorer sidebar for CMux.
# Usage:
#   bash broot-pane.sh          — toggle (keybind, e.g. Opt+E)
#   bash broot-pane.sh --open   — open only, reads hook JSON from stdin (SessionStart)
# Works with Claude Code, OpenCode, and any tool that sets CMUX_SESSION_ID.

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

[[ -z "$CMUX_WORKSPACE_ID" ]] && exit 0

MODE="toggle"
[[ "$1" == "--open" ]] && MODE="open"

# --- Toggle: close if already open ---
if [[ "$MODE" == "toggle" && -f "$BROOT_MARKER" ]]; then
    BROOT_PANE=$(cat "$BROOT_MARKER")
    if cmux tree 2>/dev/null | grep -q "$BROOT_PANE"; then
        cmux close-surface --surface "$BROOT_PANE" 2>/dev/null
        rm -f "$BROOT_MARKER"
        exit 0
    fi
    rm -f "$BROOT_MARKER"  # stale marker
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
    SESSION_ID="$(cmux_session_id)"
fi

# Get caller pane ref for refocus later
CALLER_PANE=$(cmux identify 2>/dev/null | jq -r '.caller.pane_ref' 2>/dev/null)

# Create left split
RESULT=$(cmux new-split left --surface "${CMUX_SURFACE_ID:-}" 2>&1)
BROOT_SURFACE=$(echo "$RESULT" | grep -oE 'surface:[0-9a-zA-Z-]+' | head -1)

if [[ -n "$BROOT_SURFACE" ]]; then
    echo "$BROOT_SURFACE" > "$BROOT_MARKER"
    cmux respawn-pane --surface "$BROOT_SURFACE" --command "CMUX_SESSION_ID='$SESSION_ID' exec broot '$CWD'" 2>/dev/null
fi

# Refocus caller pane
[[ -n "$CALLER_PANE" ]] && cmux focus-pane "$CALLER_PANE" 2>/dev/null

exit 0
