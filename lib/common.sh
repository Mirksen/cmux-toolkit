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
cmux_session_id() { echo "${CMUX_SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"; }
