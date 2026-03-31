#!/bin/bash
# Claude Code SessionStart hook: open a Vim pane below for Claude-Vim sync.
# CMux version. Optimized for speed (~750ms instead of ~2.9s).
#
# Marker file (~/.claude/vim-panes/<SURFACE_ID>.ref) format:
#   line 1: vim surface ref (e.g. surface:6)
#   line 2: session_id that Vim was started/rebound with

DEBUG_LOG="/tmp/claude-vim-cmux-debug.log"
log() { echo "$(date '+%H:%M:%S.%N' | cut -c1-12): $*" >> "$DEBUG_LOG"; }

[[ -z "$CMUX_WORKSPACE_ID" ]] && exit 0

INPUT=$(cat)
log "--- START ---"

# Single jq call to extract both fields
eval "$(echo "$INPUT" | jq -r '@sh "SESSION_ID=\(.session_id // "") CWD=\(.cwd // "")"')"
log "session=$SESSION_ID"
[[ -z "$SESSION_ID" ]] && exit 0

# Persist session ID for PostToolUse hook
[[ -n "$CLAUDE_ENV_FILE" ]] && echo "export CLAUDE_SESSION_ID='$SESSION_ID'" >> "$CLAUDE_ENV_FILE"

# Write session ID keyed by CWD for broot-toggle
if [[ -n "$CWD" ]]; then
    mkdir -p "$HOME/.claude/broot-panes"
    echo "$SESSION_ID" > "$HOME/.claude/broot-panes/$(echo -n "$CWD" | md5 -q).session"
fi

mkdir -p "$HOME/.claude/vim-panes"
VIM_PANE_MARKER="$HOME/.claude/vim-panes/${CMUX_SURFACE_ID}.ref"

# Get Claude's pane ref for refocus later (one cmux call, ~250ms)
CLAUDE_PANE=$(cmux identify 2>/dev/null | jq -r '.caller.pane_ref' 2>/dev/null)

# --- Resume path: check if a Vim pane already exists for this surface ---
if [[ -f "$VIM_PANE_MARKER" ]]; then
    VIM_SURFACE=$(sed -n '1p' "$VIM_PANE_MARKER")
    OLD_SESSION=$(sed -n '2p' "$VIM_PANE_MARKER")
    log "resume check: vim_surface=$VIM_SURFACE old_session=$OLD_SESSION"

    # Check if Vim is actually running by reading its screen
    if [[ -n "$VIM_SURFACE" ]]; then
        SCREEN=$(cmux read-screen --surface "$VIM_SURFACE" --lines 3 2>/dev/null)
        if echo "$SCREEN" | grep -qE "NORMAL|INSERT|VISUAL|REPLACE|COMMAND"; then
            # Vim alive — rebind to new session
            log "rebinding"
            [[ -f "$HOME/.vim/claude-open-file-$OLD_SESSION" ]] && \
                echo "::rebind::$SESSION_ID" >> "$HOME/.vim/claude-open-file-$OLD_SESSION"
            : > "$HOME/.vim/claude-open-file-$SESSION_ID"
            printf '%s\n%s\n' "$VIM_SURFACE" "$SESSION_ID" > "$VIM_PANE_MARKER"
            log "--- DONE (rebind) ---"
            exit 0
        fi
    fi

    # Vim dead — close zombie pane, clean marker
    log "zombie cleanup"
    [[ -n "$VIM_SURFACE" ]] && cmux send --surface "$VIM_SURFACE" "exit\n" 2>/dev/null
    rm -f "$VIM_PANE_MARKER"
fi

# --- Fresh start: create new Vim sub-pane ---
: > "$HOME/.vim/claude-open-file-$SESSION_ID"

# new-split returns "OK surface:N workspace:N"
NEW_SURFACE=$(cmux new-split down --surface "$CMUX_SURFACE_ID" 2>&1 | grep -oE 'surface:[0-9a-zA-Z-]+' | head -1)
[[ -z "$NEW_SURFACE" ]] && { log "ERROR: split failed"; exit 1; }
log "split: $NEW_SURFACE"

# Save marker
printf '%s\n%s\n' "$NEW_SURFACE" "$SESSION_ID" > "$VIM_PANE_MARKER"

# Start Vim — exec so pane closes when Vim exits
cmux respawn-pane --surface "$NEW_SURFACE" --command "CLAUDE_SESSION_ID='$SESSION_ID' exec vim" 2>/dev/null

# Refocus Claude pane explicitly (last-pane is unreliable with multiple panes)
[[ -n "$CLAUDE_PANE" ]] && cmux focus-pane "$CLAUDE_PANE" 2>/dev/null

log "--- DONE ---"
exit 0
