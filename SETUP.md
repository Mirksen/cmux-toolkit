# cmux-toolkit Setup

## Claude Code

Paste this into Claude Code to set up the toolkit:

---

```
Set up the cmux-toolkit (viewtab browser tabs, manual Vim, on-demand broot) for my cmux environment:

1. Clone the repo (any location is fine):
   git clone https://github.com/Mirksen/cmux-toolkit.git
   (If it already exists, run: git pull from inside the repo)

2. Run the setup script from inside the repo:
   bash setup.sh

   This handles everything: dependencies, symlinks, broot config,
   shell-init.sh (PATH + broot keybind), and Claude Code hooks.

3. Source .zshrc to activate in the current shell:
   source ~/.zshrc

4. Verify everything works:
   - All symlinks in ~/.cmux-toolkit/hooks/ point to valid targets
   - Commands available: view, viewtab, edit, edittab
   - broot starts: broot --version
   - Vim has cmux-sync: grep cmux-sync ~/.vimrc

5. Tell me what manual steps remain.
```

---

## OpenCode

After running `setup.sh`, OpenCode support is automatic — the adapter plugin is symlinked to `~/.config/opencode/plugins/cmux-toolkit` and loaded on startup. No extra configuration needed.

---

## What it does

After setup, every AI coding session in cmux automatically gets:
- **Browser tabs with diff highlighting** — files edited appear as rendered browser tabs with changes highlighted in green
- **Manual Vim** — open any file in Vim via `! edit file` or `! edittab file`
- **Manual view** — render any file in browser via `! view file` or `! viewtab file`
- **broot file browser** — toggle with **Option + Arrow Up** (on-demand, not automatic)

## Optional: auto Vim subpane (Claude Code)

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
