"""cmux-toolkit shared config — imported by all Python hooks."""
import os

CMUX_STATE_DIR = os.path.expanduser("~/.cmux-toolkit")
VIEW_CHANGES_DIR = os.path.join(CMUX_STATE_DIR, "view-changes")
VIEW_SURFACES_DIR = os.path.join(CMUX_STATE_DIR, "view-surfaces")
VIM_PANES_DIR = os.path.join(CMUX_STATE_DIR, "vim-panes")
BROOT_PANES_DIR = os.path.join(CMUX_STATE_DIR, "broot-panes")
SIGNAL_PREFIX = os.path.expanduser("~/.vim/cmux-open-file")


def signal_file_for(session_id):
    return f"{SIGNAL_PREFIX}-{session_id}"
