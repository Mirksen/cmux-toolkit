#!/bin/bash
# Claude Code SessionEnd hook: clean up broot marker files.
# The broot pane itself dies when the terminal tab/workspace closes.

rm -f "$HOME/.claude/broot-pane-tty" 2>/dev/null    # iTerm2 marker
rm -f "$HOME/.claude/broot-pane-id" 2>/dev/null      # CMux marker
exit 0
