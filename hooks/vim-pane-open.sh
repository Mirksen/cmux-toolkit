#!/bin/bash
# Claude Code SessionStart hook: open a Vim pane below for Claude-Vim sync.
# Each Claude session gets its own Vim pane, bound by session_id.
# On /resume: reuses the existing Vim pane, rebinds it to the new session.
# Only runs in iTerm2.

if [[ "$TERM_PROGRAM" != "iTerm.app" ]]; then
    exit 0
fi

INPUT=$(cat)

echo "$INPUT" > /tmp/claude-vim-hook-debug.json

SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

if [[ -z "$SESSION_ID" ]]; then
    exit 0
fi

# Persist session ID so PostToolUse hook and Vim can use it
if [[ -n "$CLAUDE_ENV_FILE" ]]; then
    echo "export CLAUDE_SESSION_ID='$SESSION_ID'" >> "$CLAUDE_ENV_FILE"
fi

# Write session ID to a well-known file that broot-toggle can read.
# Key by CWD (hashed) — each project dir maps to one active session.
CWD=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)
if [[ -n "$CWD" ]]; then
    mkdir -p "$HOME/.claude/broot-panes"
    CWD_HASH=$(echo -n "$CWD" | md5 -q)
    echo "$SESSION_ID" > "$HOME/.claude/broot-panes/${CWD_HASH}.session"
fi

# Check if a Vim pane already exists in this tab
VIM_RUNNING=$(osascript <<'APPLESCRIPT'
tell application "iTerm2"
    tell current tab of current window
        repeat with aSession in sessions
            set sessionName to (name of aSession)
            if sessionName contains "vim" or sessionName contains "Vim" then
                return "yes"
            end if
        end repeat
    end tell
end tell
return "no"
APPLESCRIPT
)

if [[ "$VIM_RUNNING" == "yes" ]]; then
    # Vim pane exists (e.g. /resume) — rebind it to the new session.
    # Find the old signal file that Vim is currently polling and write
    # a ::rebind:: directive so Vim switches to the new session's file.
    OLD_SIGNAL=$(ls -t "$HOME"/.vim/claude-open-file-????????-????-????-????-???????????? 2>/dev/null | head -1)
    if [[ -n "$OLD_SIGNAL" ]]; then
        echo "::rebind::$SESSION_ID" >> "$OLD_SIGNAL"
    fi
    # Also create the new session's signal file (truncate to avoid stale ::quit::)
    : > "$HOME/.vim/claude-open-file-$SESSION_ID"
    exit 0
fi

# No Vim pane — create one
osascript <<APPLESCRIPT
tell application "iTerm2"
    tell current session of current tab of current window
        set newSession to (split horizontally with default profile command "env CLAUDE_SESSION_ID='$SESSION_ID' vim")
    end tell
end tell
APPLESCRIPT

exit 0
