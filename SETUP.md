# cmux-toolkit Setup

Paste this into Claude Code to set up the broot + vim subpane integration for cmux:

---

```
Set up the cmux-toolkit (broot file browser + vim subpane integration) for my cmux environment:

1. Clone the repo:
   git clone https://github.com/Mirksen/cmux-toolkit.git ~/cmux-toolkit
   (If it already exists, run: git -C ~/cmux-toolkit pull)

2. Run the setup script:
   bash ~/cmux-toolkit/setup.sh

3. Add the broot-toggle keybind to my .zshrc — append this block
   if it's not already present:

   # === broot sidebar toggle (Opt+ArrowUp) ===
   source "$HOME/.config/broot/launcher/bash/br"
   broot-toggle() {
       bash ~/.claude/hooks/broot-pane-toggle-dispatch.sh
       zle reset-prompt
   }
   zle -N broot-toggle
   bindkey '\e[1;3A' broot-toggle

4. Merge these hooks into my ~/.claude/settings.json (keep my existing
   env, permissions, and model settings — only add/merge the hooks section):

   "hooks": {
     "UserPromptSubmit": [
       { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-prompt-reset.sh" }] }
     ],
     "SessionStart": [
       { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open-dispatch.sh" }] },
       { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/broot-pane-open.sh" }] },
       { "matcher": "resume",  "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open-dispatch.sh" }] }
     ],
     "PostToolUse": [
       { "matcher": "Read|Edit|Write", "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vim-open-file.py" }] }
     ],
     "SessionEnd": [
       { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-close.sh" }] },
       { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/broot-pane-close.sh" }] }
     ]
   }

5. Verify everything works:
   - All symlinks in ~/.claude/hooks/ point to valid targets
   - broot starts: broot --version
   - Vim has claude-sync: grep claude-sync ~/.vimrc
   - Signal file dir exists: ls ~/.vim/

6. Tell me what manual steps remain.
```

---

## What it does

After setup, every Claude Code session in cmux automatically gets:
- **Vim subpane** (below) — files Claude reads/edits open here in real-time
- **broot file browser** (left sidebar) — toggle with **Option + Arrow Up**
- Selecting a file in broot opens it in the Vim subpane

## Updating

```bash
git -C ~/cmux-toolkit pull && bash ~/cmux-toolkit/setup.sh
```
