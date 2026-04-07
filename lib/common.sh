#!/bin/bash
# cmux-toolkit shared config — sourced by all shell hooks.
# Usage: source "$(dirname "$(readlink -f "$0")")/../lib/common.sh"

CMUX_STATE_DIR="$HOME/.cmux-toolkit"
VIEW_CHANGES_DIR="$CMUX_STATE_DIR/view-changes"
VIEW_SURFACES_DIR="$CMUX_STATE_DIR/view-surfaces"
VIM_PANES_DIR="$CMUX_STATE_DIR/vim-panes"
BROOT_PANES_DIR="$CMUX_STATE_DIR/broot-panes"
BROOT_MARKER="$CMUX_STATE_DIR/broot-pane-id"
SIGNAL_PREFIX="$HOME/.vim/cmux-open-file"

cmux_signal_file() { echo "${SIGNAL_PREFIX}-$1"; }
cmux_hash() { if command -v md5 &>/dev/null; then echo -n "$1" | md5 -q; else echo -n "$1" | md5sum | cut -d' ' -f1; fi; }
cmux_session_id() {
    # 1. Explicit env var (set by spawn commands or tool plugins)
    [[ -n "${CMUX_SESSION_ID:-}" ]] && echo "$CMUX_SESSION_ID" && return
    # 2. State file keyed by CWD (written by vim-pane-open.sh)
    local hash; hash="$(cmux_hash "$(pwd)")"
    local state="$BROOT_PANES_DIR/${hash}.session"
    [[ -f "$state" ]] && cat "$state" && return
    # 3. Fallback
    echo "default"
}
