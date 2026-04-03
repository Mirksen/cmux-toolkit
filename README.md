# cmux-toolkit

Visual feedback and file tools for Claude Code in [cmux](https://cmux.dev) — browser tabs with diff highlighting, manual Vim editing, and on-demand broot file browser.

## What you get

When Claude edits a file, a **browser tab** opens automatically showing the rendered result with changes highlighted in green:

```
┌──────────────────────────────────────────────┐
│  Claude Code                                 │
│  ┌────────────────────────────────────────┐  │
│  │ PostToolUse (Edit|Write)               │  │
│  │  → view-open-file.py → viewtab        │  │
│  │  → browser tab with diff highlighting  │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  Manual commands (via ! prefix):             │
│  • ! edit file.py    → Vim in split pane     │
│  • ! edittab file.py → Vim as tab            │
│  • ! view file.md    → rendered browser view │
│  • ! viewtab file.md → browser tab           │
│                                              │
│  On-demand (keyboard shortcut):              │
│  • Opt+↑  → toggle broot file browser        │
│    Enter in broot → viewtab or Vim IPC       │
└──────────────────────────────────────────────┘
```

- **viewtab** (automatic) — every file Claude edits/writes opens as a browser tab with diff highlighting (green background, auto-scroll to changes)
- **edit / edittab** (manual) — open files in Vim via `! edit` or `! edittab` in Claude Code
- **view / viewtab** (manual) — render any file in the browser via `! view` or `! viewtab`
- **broot sidebar** (on-demand) — toggle with `Option + Arrow Up`, select files to open

## Quick start

See [SETUP.md](SETUP.md) for the copy-paste instruction you give to Claude Code.

Or manually:

```bash
git clone https://github.com/Mirksen/cmux-toolkit.git ~/cmux-toolkit
bash ~/cmux-toolkit/setup.sh
```

Then add the hooks to your `~/.claude/settings.json` and the keybind to your `.zshrc` (see SETUP.md for details).

## How it works

### viewtab (automatic, primary)

When Claude Code runs Edit or Write, the `view-open-file.py` PostToolUse hook:
1. Captures the file path and new content
2. Writes the diff to a temp file
3. Calls `viewtab` which renders the file as HTML with changes highlighted
4. Opens a browser tab in the same cmux pane
5. Auto-scrolls to the changed section

File types supported:
- **Markdown** — rendered via `marked --gfm` with clean CSS
- **Code files** — syntax-highlighted via Prism.js (Python, Bash, JS, TS, YAML, JSON, TOML)
- **PDF, HTML, images** — opened natively

Old tabs are automatically closed when a new prompt starts (`view-prompt-reset.sh`).

### edit / edittab (manual)

Open files in Vim from Claude Code using the `!` prefix:
- `! edit file.py` — opens Vim in a new split pane below
- `! edittab file.py` — opens Vim as a tab in the same pane

If you use Vim with `claude-sync.vim`, broot's Enter key sends files to Vim via signal file IPC.

### broot sidebar (on-demand)

Toggle with **Option + Arrow Up**. When you press Enter on a file in broot:
1. If Vim is running (signal file exists) → sends file to Vim
2. If viewtab is available → opens browser tab
3. Fallback → opens Vim in a split pane

## Hook architecture

```
PostToolUse  ─→ view-open-file.py ─────→ viewtab → browser tab with diff

UserPromptSubmit ─→ view-prompt-reset.sh → closes old browser tabs

SessionEnd   ─→ view-close.sh ─────────→ closes all browser tabs
             ─→ broot-pane-close.sh ───→ cleans up broot marker files

PreToolUse   ─→ fix-whitespace-escape.py → fixes iCloud path escaping

Keybind      ─→ broot-pane-toggle-dispatch.sh → cmux: broot-pane-toggle-cmux.sh
  (Opt+↑)                                      iTerm2: broot-pane-toggle.sh
```

### Optional: auto Vim subpane

If you prefer the old behavior where Vim opens automatically on session start, add these SessionStart hooks to your settings.json:

```json
"SessionStart": [
  { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open-dispatch.sh" }] },
  { "matcher": "resume",  "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open-dispatch.sh" }] }
]
```

And add the vim PostToolUse hook:

```json
{ "matcher": "Read|Edit|Write", "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vim-open-file.py" }] }
```

### Optional: auto broot sidebar

To auto-open broot on session start, add:

```json
"SessionStart": [
  { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/broot-pane-open.sh" }] }
]
```

## Structure

```
cmux-toolkit/
├── bin/                        # User-facing commands (→ ~/.local/bin/)
│   ├── view                    # Render file in cmux browser
│   ├── viewtab → view          # Tab mode (via $0 detection)
│   ├── edit                    # Open Vim in cmux pane
│   └── edittab → edit          # Tab mode (via $0 detection)
├── hooks/                      # Claude Code hooks (→ ~/.claude/hooks/)
│   ├── view-open-file.py       # PostToolUse → browser tab with diff
│   ├── view-prompt-reset.sh    # UserPromptSubmit → close old tabs
│   ├── view-close.sh           # SessionEnd → close all tabs
│   ├── broot-pane-toggle-*.sh  # Opt+↑ broot sidebar toggle
│   ├── broot-pane-close.sh     # SessionEnd → broot cleanup
│   ├── broot-open-file.sh      # broot Enter → viewtab or Vim
│   ├── vim-*.sh / vim-*.py     # Optional Vim subpane lifecycle
│   └── fix-whitespace-escape.py  # iCloud path fix
├── config/
│   ├── broot/                  # broot configuration
│   │   ├── conf.hjson
│   │   ├── verbs.hjson         # Enter key → open-file verb
│   │   └── skins/
│   └── vim/
│       └── claude-sync.vim     # Vim signal file polling
├── setup.sh                    # Idempotent setup script
├── SETUP.md                    # Copy-paste instructions for Claude Code
└── README.md
```

## Requirements

- macOS with [Homebrew](https://brew.sh)
- [cmux](https://cmux.dev) terminal multiplexer
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [Node.js](https://nodejs.org) (for Markdown rendering via `npx marked`)
- `broot` and `jq` (installed automatically by setup.sh)

## Updating

```bash
git -C ~/cmux-toolkit pull && bash ~/cmux-toolkit/setup.sh
```

Symlinks point to the repo, so most updates are instant after `git pull`.
