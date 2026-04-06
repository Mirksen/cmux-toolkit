#!/bin/bash
# Claude Code SessionEnd hook: clean up all session resources.
# Handles Vim pane, broot marker, and browser view surfaces.
# Only fires on actual exit, not on /resume.

INPUT=$(cat)
eval "$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'SESSION_ID={d.get(\"session_id\",\"\")}')
print(f'REASON={d.get(\"reason\",\"\")}')
" 2>/dev/null)"

[[ -z "$SESSION_ID" ]] && exit 0
[[ "$REASON" == "resume" ]] && exit 0

# --- Vim: signal quit and remove marker ---
SIGNAL_FILE="$HOME/.vim/claude-open-file-$SESSION_ID"
echo "::quit::" > "$SIGNAL_FILE"

if [[ -n "$CMUX_SURFACE_ID" ]]; then
    rm -f "$HOME/.claude/vim-panes/${CMUX_SURFACE_ID}.ref"
elif [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    rm -f "$HOME/.claude/vim-panes/${CMUX_WORKSPACE_ID}.ref"
fi

# --- Broot: remove marker ---
rm -f "$HOME/.claude/broot-pane-id" 2>/dev/null

# --- View surfaces: close all tracked browser tabs ---
TRACKING_FILE="$HOME/.claude/view-surfaces/${SESSION_ID}.txt"
if [[ -f "$TRACKING_FILE" ]]; then
    TREE=$(cmux tree 2>/dev/null || true)
    while IFS= read -r surface_ref; do
        [[ -z "$surface_ref" ]] && continue
        echo "$TREE" | grep -qF "$surface_ref" || continue
        cmux close-surface --surface "$surface_ref" 2>/dev/null || true
    done < "$TRACKING_FILE"
    rm -f "$TRACKING_FILE"
fi

exit 0
