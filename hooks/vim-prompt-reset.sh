#!/bin/bash
# Claude Code UserPromptSubmit hook: signal Vim to wipe previous-prompt buffers.
# Writes ::reset:: to the session signal file before Claude processes the prompt.

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

if [[ -z "$SESSION_ID" ]]; then
    exit 0
fi

SIGNAL_FILE="$HOME/.vim/claude-open-file-$SESSION_ID"

if [[ -d "$(dirname "$SIGNAL_FILE")" ]]; then
    echo "::reset::" >> "$SIGNAL_FILE"
fi

exit 0
