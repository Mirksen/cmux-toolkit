# cmux-toolkit Setup

Paste this into Claude Code to set up the toolkit:

---

```
Set up the cmux-toolkit (viewtab browser tabs, manual Vim, on-demand broot) for my cmux environment:

1. Clone the repo (any location is fine):
   git clone https://github.com/Mirksen/cmux-toolkit.git
   (If it already exists, run: git pull from inside the repo)

2. Run the setup script from inside the repo:
   bash setup.sh

3. Add the broot-toggle keybind to my .zshrc — append this block
   if it's not already present:

   # === broot sidebar toggle (Opt+ArrowUp) ===
   source "$HOME/.config/broot/launcher/bash/br"
   broot-toggle() {
       bash ~/.claude/hooks/broot-pane.sh
       zle reset-prompt
   }
   zle -N broot-toggle
   bindkey '\e[1;3A' broot-toggle

4. Ensure ~/.local/bin is in PATH — add to .zshrc if not present:

   export PATH="$HOME/.local/bin:$PATH"

5. Merge these hooks into my ~/.claude/settings.json (keep my existing
   env, permissions, and model settings — only add/merge the hooks section):

   "hooks": {
     "UserPromptSubmit": [
       { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/view-prompt-reset.sh" }] }
     ],
     "PreToolUse": [
       { "matcher": "Bash", "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/fix-whitespace-escape.py" }] }
     ],
     "PostToolUse": [
       { "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/view-open-file.py" }] }
     ],
     "SessionEnd": [
       { "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/session-cleanup.sh" }] }
     ]
   }

6. Verify everything works:
   - All symlinks in ~/.claude/hooks/ point to valid targets
   - Commands available: viewtab --help, edit --help
   - broot starts: broot --version
   - Vim has claude-sync: grep claude-sync ~/.vimrc
   - npx available: npx --version

7. Tell me what manual steps remain.
```

---

## What it does

After setup, every Claude Code session in cmux automatically gets:
- **Browser tabs with diff highlighting** — files Claude edits appear as rendered browser tabs with changes highlighted in green
- **Manual Vim** — open any file in Vim via `! edit file` or `! edittab file`
- **Manual view** — render any file in browser via `! view file` or `! viewtab file`
- **broot file browser** — toggle with **Option + Arrow Up** (on-demand, not automatic)

## Optional: auto Vim subpane

To also auto-open a Vim subpane on session start (old behavior), add these to the hooks in settings.json:

```json
"SessionStart": [
  { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open.sh" }] },
  { "matcher": "resume",  "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open.sh" }] }
],
"PostToolUse": [
  { "matcher": "Read|Edit|Write", "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vim-open-file.py" }] }
]
```

## Updating

```bash
git pull && bash setup.sh
```
