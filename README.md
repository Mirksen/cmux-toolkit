# cmux-toolkit

Visual feedback and file tools for Claude Code in [cmux](https://cmux.dev) — browser tabs with diff highlighting, manual Vim editing, and on-demand broot file browser.

## What you get

When Claude edits files, a **browser tab** opens automatically showing a combined diff view with VS Code-style sidebar and git status badges:

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

- **viewtab** (automatic) — all files Claude edits/writes appear in a combined browser view with sidebar, diff highlighting (green additions, red deletions), and git status badges (U/A/M/D/R)
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
1. Appends the edit info (file, old/new content) to a session changes log (JSONL)
2. Renders a **combined HTML page** with a VS Code-style sidebar and collapsible diff sections for all changed files
3. Navigates the existing browser tab (or creates one) to the combined page
4. Auto-scrolls to the first changed section

The combined view includes:
- **Sidebar** — file tree (from `git ls-files`) with changes list, status badges, and click-to-navigate
- **Status badges** — follows VS Code git conventions: **U** (untracked, green), **A** (added, green), **M** (modified, yellow), **D** (deleted, red), **R** (renamed, teal)
- **Diff highlighting** — added lines in green, deleted lines in red with strikethrough, collapsible context
- **Dark mode** — automatic via `prefers-color-scheme`

File types supported:
- **Markdown** — rendered via `marked` (Node.js) with clean CSS
- **Code files** — syntax-highlighted via Prism.js (Python, Bash, JS, TS, YAML, JSON, TOML, and more)
- **PDF, HTML, images** — opened natively (via `! view` / `! viewtab` commands)

The changes log resets when a new prompt starts (`view-prompt-reset.sh`).

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

SessionEnd   ─→ session-cleanup.sh ───→ closes vim, broot, browser tabs

PreToolUse   ─→ fix-whitespace-escape.py → fixes iCloud path escaping

Keybind      ─→ broot-pane.sh ──────→ toggle broot sidebar
  (Opt+↑)
```

### Optional: auto Vim subpane

If you prefer the old behavior where Vim opens automatically on session start, add these SessionStart hooks to your settings.json:

```json
"SessionStart": [
  { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open.sh" }] },
  { "matcher": "resume",  "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/vim-pane-open.sh" }] }
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
  { "matcher": "startup", "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/broot-pane.sh --open" }] }
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
│   ├── view-open-file.py       # PostToolUse → combined browser view with diffs
│   ├── view-prompt-reset.sh    # UserPromptSubmit → reset changes log
│   ├── session-cleanup.sh      # SessionEnd → close vim, broot, browser
│   ├── fix-whitespace-escape.py  # PreToolUse → iCloud path fix
│   ├── broot-pane.sh           # Opt+↑ broot sidebar toggle / --open
│   ├── broot-open-file.sh      # broot Enter → viewtab or Vim
│   ├── vim-pane-open.sh        # Optional: auto Vim subpane on start
│   ├── vim-open-file.py        # Optional: send file paths to Vim
│   ├── vim-prompt-reset.sh     # Optional: reset Vim buffers on prompt
│   └── templates/              # HTML assets for view-open-file.py
│       ├── view-changes.css    # Sidebar, diff, and dark mode styles
│       └── view-changes.js     # Tree navigation and diff toggle logic
├── config/
│   ├── cmux/
│   │   └── config.ghostty      # Dark theme + inactive pane dimming
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

## Terminal theme

The toolkit includes a dark Ghostty theme with **inactive pane dimming** — unfocused panes get a gray overlay so the active pane stands out visually.

Install:
```bash
cp ~/cmux-toolkit/config/cmux/config.ghostty \
   ~/Library/Application\ Support/com.cmuxterm.app/config.ghostty
```

Or let `setup.sh` handle it (symlinks automatically).

The theme uses MesloLGS Nerd Font — install via `brew install font-meslo-lg-nerd-font`.

## Requirements

- macOS with [Homebrew](https://brew.sh)
- [cmux](https://cmux.dev) terminal multiplexer
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [Node.js](https://nodejs.org) + `marked` package (for Markdown rendering)
- `broot` and `jq` (installed automatically by setup.sh)

## Updating

```bash
git -C ~/cmux-toolkit pull && bash ~/cmux-toolkit/setup.sh
```

Symlinks point to the repo, so most updates are instant after `git pull`.
