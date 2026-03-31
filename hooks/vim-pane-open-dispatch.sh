#!/bin/bash
# Dispatcher: routes to iTerm2 or CMux version of vim-pane-open
# Used as SessionStart hook — auto-detects terminal.
# Pipes stdin through (hook JSON) since exec replaces the process.

DEBUG_LOG="/tmp/claude-vim-dispatch-debug.log"
echo "$(date): dispatch called, CMUX_WORKSPACE_ID='$CMUX_WORKSPACE_ID' TERM_PROGRAM='$TERM_PROGRAM'" >> "$DEBUG_LOG"

if [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    echo "$(date): routing to cmux hook" >> "$DEBUG_LOG"
    exec bash ~/.claude/hooks/vim-pane-open-cmux.sh
else
    echo "$(date): routing to iterm hook" >> "$DEBUG_LOG"
    exec bash ~/.claude/hooks/vim-pane-open.sh
fi
