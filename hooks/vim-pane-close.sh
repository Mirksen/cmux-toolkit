#!/bin/bash
# Claude Code SessionEnd hook: signal the bound Vim pane to close.
# Only fires on actual exit, not on /resume.

INPUT=$(cat)

echo "$INPUT" > /tmp/claude-vim-close-debug.json

# Parse reason and session_id
eval "$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'SESSION_ID={d.get(\"session_id\",\"\")}')
print(f'REASON={d.get(\"reason\",\"\")}')
" 2>/dev/null)"

if [[ -z "$SESSION_ID" ]]; then
    exit 0
fi

# /resume triggers SessionEnd with reason="resume" — don't kill Vim
if [[ "$REASON" == "resume" ]]; then
    exit 0
fi

SIGNAL_FILE="$HOME/.vim/claude-open-file-$SESSION_ID"
echo "::quit::" > "$SIGNAL_FILE"

# Clean up CMux vim pane marker (per-surface)
if [[ -n "$CMUX_SURFACE_ID" ]]; then
    rm -f "$HOME/.claude/vim-panes/${CMUX_SURFACE_ID}.ref"
elif [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    rm -f "$HOME/.claude/vim-panes/${CMUX_WORKSPACE_ID}.ref"
else
    rm -f "$HOME/.claude/vim-pane-ref"
fi

exit 0
