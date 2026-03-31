#!/bin/bash
# Claude Code SessionStart hook: open broot file explorer as a left vertical split.
# Runs AFTER vim-pane-open.sh — the Vim pane must exist first.
# Dispatches to CMux or iTerm2 version.

# CMux: delegate to cmux-specific script
if [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    exec bash ~/.claude/hooks/broot-pane-open-cmux.sh
fi

# iTerm2 only below
if [[ "$TERM_PROGRAM" != "iTerm.app" ]]; then
    exit 0
fi

# Read hook JSON from stdin
INPUT=$(cat)

# Extract session_id
SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

if [[ -z "$SESSION_ID" ]]; then
    exit 0
fi

# Brief delay to let Vim pane settle (vim-pane-open.sh runs first)
sleep 0.5

CWD=$(pwd)

# Split vertically from the Claude pane (session 1) — broot appears on the left.
# Pass CLAUDE_SESSION_ID so broot's vim-open verb can write to the correct signal file.
osascript <<APPLESCRIPT
tell application "iTerm2"
    tell current tab of current window
        tell session 1
            set brootSession to (split vertically with default profile command "env CLAUDE_SESSION_ID='$SESSION_ID' broot '$CWD'")
        end tell
    end tell
end tell
APPLESCRIPT

exit 0
