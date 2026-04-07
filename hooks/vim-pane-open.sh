#!/bin/bash
# SessionStart hook: open a Vim pane below for AI-Vim sync.
# Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.
#
# Marker file (~/.cmux-toolkit/vim-panes/<SURFACE_ID>.ref) format:
#   line 1: vim surface ref (e.g. surface:6)
#   line 2: session_id that Vim was started/rebound with

source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

DEBUG_LOG="/tmp/cmux-vim-debug.log"
log() { echo "$(date '+%H:%M:%S.%N' | cut -c1-12): $*" >> "$DEBUG_LOG"; }

[[ -z "$CMUX_WORKSPACE_ID" ]] && exit 0

INPUT=$(cat)
log "--- START ---"

# Single jq call to extract both fields
eval "$(echo "$INPUT" | jq -r '@sh "SESSION_ID=\(.session_id // "") CWD=\(.cwd // "")"')"
log "session=$SESSION_ID"
[[ -z "$SESSION_ID" ]] && exit 0

# Write session ID keyed by CWD (used by broot-toggle and cmux_session_id)
if [[ -n "$CWD" ]]; then
    mkdir -p "$BROOT_PANES_DIR"
    echo "$SESSION_ID" > "$BROOT_PANES_DIR/$(cmux_hash "$CWD").session"
fi

mkdir -p "$VIM_PANES_DIR"
VIM_PANE_MARKER="$VIM_PANES_DIR/${CMUX_SURFACE_ID}.ref"

# Get caller pane ref for refocus later (one cmux call, ~250ms)
CALLER_PANE=$(cmux identify 2>/dev/null | jq -r '.caller.pane_ref' 2>/dev/null)

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
            OLD_SIGNAL="$(cmux_signal_file "$OLD_SESSION")"
            [[ -f "$OLD_SIGNAL" ]] && echo "::rebind::$SESSION_ID" >> "$OLD_SIGNAL"
            : > "$(cmux_signal_file "$SESSION_ID")"
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
: > "$(cmux_signal_file "$SESSION_ID")"

# new-split returns "OK surface:N workspace:N"
NEW_SURFACE=$(cmux new-split down --surface "$CMUX_SURFACE_ID" 2>&1 | grep -oE 'surface:[0-9a-zA-Z-]+' | head -1)
[[ -z "$NEW_SURFACE" ]] && { log "ERROR: split failed"; exit 1; }
log "split: $NEW_SURFACE"

# Save marker
printf '%s\n%s\n' "$NEW_SURFACE" "$SESSION_ID" > "$VIM_PANE_MARKER"

# Start Vim — exec so pane closes when Vim exits
cmux respawn-pane --surface "$NEW_SURFACE" --command "CMUX_SESSION_ID='$SESSION_ID' exec vim" 2>/dev/null

# Refocus caller pane explicitly (last-pane is unreliable with multiple panes)
[[ -n "$CALLER_PANE" ]] && cmux focus-pane "$CALLER_PANE" 2>/dev/null

log "--- DONE ---"
exit 0
