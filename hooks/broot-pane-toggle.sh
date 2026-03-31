#!/bin/bash
# Toggle broot file explorer sidebar in iTerm2.
# Opens a vertical split with broot, or closes the existing broot pane.
# Usage: bash ~/.claude/hooks/broot-pane-toggle.sh

if [[ "$TERM_PROGRAM" != "iTerm.app" ]]; then
    echo "Not running in iTerm2" >&2
    exit 1
fi

MARKER="$HOME/.claude/broot-pane-tty"

# Check if broot is already running in a tracked pane
if [[ -f "$MARKER" ]]; then
    BROOT_TTY=$(cat "$MARKER")
    TTY_BASE=$(basename "$BROOT_TTY")
    # Check if that tty still has a broot process
    if pgrep -t "$TTY_BASE" broot >/dev/null 2>&1; then
        # broot is running — close its pane
        osascript -e "
            tell application \"iTerm2\"
                tell current tab of current window
                    repeat with aSession in sessions
                        if (tty of aSession) is equal to \"$BROOT_TTY\" then
                            close aSession
                        end if
                    end repeat
                end tell
            end tell
        "
        rm -f "$MARKER"
        exit 0
    else
        # Stale marker — broot died, clean up
        rm -f "$MARKER"
    fi
fi

# broot not running — create a vertical split and launch it
CWD=$(pwd)
SESSION_ID="${CLAUDE_SESSION_ID:-default}"

osascript <<APPLESCRIPT
tell application "iTerm2"
    tell current session of current tab of current window
        set brootSession to (split vertically with default profile command "env CLAUDE_SESSION_ID='$SESSION_ID' broot '$CWD'")
        set ttyPath to (tty of brootSession)
        do shell script "echo " & quoted form of ttyPath & " > $HOME/.claude/broot-pane-tty"
    end tell
end tell
APPLESCRIPT

exit 0
