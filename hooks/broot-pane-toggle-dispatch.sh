#!/bin/bash
# Dispatcher: routes to iTerm2 or CMux version of broot-pane-toggle
# Used as keybinding (Alt+E) — auto-detects terminal.

if [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    exec bash ~/.claude/hooks/broot-pane-toggle-cmux.sh
else
    exec bash ~/.claude/hooks/broot-pane-toggle.sh
fi
