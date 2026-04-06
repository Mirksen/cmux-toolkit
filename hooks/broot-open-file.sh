#!/bin/bash
# broot verb: open file
# - With CLAUDE_SESSION_ID + active Vim signal file: write to signal file (Vim picks it up)
# - Otherwise: open file in viewtab (browser tab)
# - Fallback: open Vim in a split pane below

FILE="$1"

# --- Path 1: Claude session with Vim signal file → Vim IPC ---
if [[ -n "$CLAUDE_SESSION_ID" && "$CLAUDE_SESSION_ID" != "default" ]]; then
    SIGNAL="$HOME/.vim/claude-open-file-$CLAUDE_SESSION_ID"
    if [[ -f "$SIGNAL" ]]; then
        echo "$FILE" >> "$SIGNAL"
        exit 0
    fi
fi

# --- Path 2: viewtab available → open as browser tab ---
if command -v viewtab &>/dev/null && [[ -n "$CMUX_WORKSPACE_ID" ]]; then
    viewtab "$FILE" &>/dev/null
    exit 0
fi

# --- Path 3: Standalone mode — open Vim in a split pane ---
SIGNAL="$HOME/.vim/claude-open-file-standalone"
MARKER="$HOME/.claude/broot-panes/standalone-vim-ref"

# Check if standalone Vim is already running
if [[ -f "$MARKER" ]]; then
    VIM_REF=$(cat "$MARKER")
    if cmux list-panes 2>/dev/null | grep -q "$VIM_REF"; then
        echo "$FILE" >> "$SIGNAL"
        exit 0
    fi
    rm -f "$MARKER"
fi

# No Vim running — open one in a split below
mkdir -p "$HOME/.claude/broot-panes"
echo "$FILE" > "$SIGNAL"
ESCAPED_FILE=$(printf '%q' "$FILE")

RESULT=$(cmux new-split down 2>&1)
VIM_SURFACE=$(echo "$RESULT" | grep -oE 'surface:[0-9a-zA-Z-]+' | head -1)
if [[ -n "$VIM_SURFACE" ]]; then
    echo "$VIM_SURFACE" > "$MARKER"
    sleep 0.5
    cmux send --surface "$VIM_SURFACE" "CLAUDE_SESSION_ID=standalone exec vim $ESCAPED_FILE" 2>/dev/null
    cmux send-key --surface "$VIM_SURFACE" Enter 2>/dev/null
fi

exit 0
