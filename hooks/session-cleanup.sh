#!/bin/bash
# SessionEnd hook: clean up all session resources.
# Handles Vim pane, broot marker, and browser view surfaces.
# Only fires on actual exit, not on /resume.
# Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

INPUT=$(cat)
eval "$(echo "$INPUT" | jq -r '@sh "SESSION_ID=\(.session_id // "") REASON=\(.reason // "")"')"

[[ -z "$SESSION_ID" ]] && exit 0
[[ "$REASON" == "resume" ]] && exit 0

# --- Vim: signal quit and remove marker ---
SIGNAL_FILE="$(cmux_signal_file "$SESSION_ID")"
echo "::quit::" > "$SIGNAL_FILE"

if [[ -n "$CMUX_SURFACE_ID" ]]; then
    rm -f "$VIM_PANES_DIR/${CMUX_SURFACE_ID}.ref"
elif [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    rm -f "$VIM_PANES_DIR/${CMUX_WORKSPACE_ID}.ref"
fi

# --- Broot: remove marker ---
rm -f "$BROOT_MARKER" 2>/dev/null

# --- View surfaces: close all tracked browser tabs ---
TRACKING_FILE="$VIEW_SURFACES_DIR/${SESSION_ID}.txt"
if [[ -f "$TRACKING_FILE" ]]; then
    TREE=$(cmux tree 2>/dev/null || true)
    while IFS= read -r surface_ref; do
        [[ -z "$surface_ref" ]] && continue
        echo "$TREE" | grep -qF "$surface_ref" || continue
        cmux close-surface --surface "$surface_ref" 2>/dev/null || true
    done < "$TRACKING_FILE"
    rm -f "$TRACKING_FILE"
fi

# --- Clean up changes logs ---
rm -f "$VIEW_CHANGES_DIR/${SESSION_ID}.jsonl" "$VIEW_CHANGES_DIR/${SESSION_ID}-all.jsonl" 2>/dev/null

exit 0
