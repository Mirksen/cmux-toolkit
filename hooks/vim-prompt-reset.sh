#!/bin/bash
# UserPromptSubmit hook: signal Vim to wipe previous-prompt buffers.
# Writes ::reset:: to the session signal file before the tool processes the prompt.
# Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

if [[ -z "$SESSION_ID" ]]; then
    exit 0
fi

SIGNAL_FILE="$(cmux_signal_file "$SESSION_ID")"

if [[ -d "$(dirname "$SIGNAL_FILE")" ]]; then
    echo "::reset::" >> "$SIGNAL_FILE"
fi

exit 0
