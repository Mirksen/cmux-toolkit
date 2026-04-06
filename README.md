# cmux-toolkit

Visual feedback and file tools for AI coding assistants in [cmux](https://cmux.dev) — browser tabs with diff highlighting, manual Vim editing, and on-demand broot file browser.

**Supported tools:** Claude Code, OpenCode (Codex CLI planned once hook support expands)

## What you get

When your AI tool edits files, a **browser tab** opens automatically showing a combined diff view with VS Code-style sidebar and git status badges:

```
┌──────────────────────────────────────────────┐
│  AI coding tool (Claude Code / OpenCode)     │
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

- **viewtab** (automatic) — all files edited/written appear in a combined browser view with sidebar, diff highlighting (green additions, red deletions), and git status badges (U/A/M/D/R)
- **edit / edittab** (manual) — open files in Vim via `! edit` or `! edittab`
- **view / viewtab** (manual) — render any file in the browser via `! view` or `! viewtab`
- **broot sidebar** (on-demand) — toggle with `Option + Arrow Up`, select files to open

## Quick start

```bash
git clone https://github.com/Mirksen/cmux-toolkit.git ~/cmux-toolkit
bash ~/cmux-toolkit/setup.sh
```

### Claude Code

See [SETUP.md](SETUP.md) for the copy-paste instruction you give to Claude Code. After running `setup.sh`, add the hooks to your `~/.claude/settings.json` and the keybind to your `.zshrc`.

### OpenCode

The `setup.sh` script auto-detects OpenCode and symlinks the adapter plugin to `~/.config/opencode/plugins/cmux-toolkit`. The plugin is loaded automatically — no extra configuration needed.

## How it works

### viewtab (automatic, primary)

When your AI tool runs Edit or Write, the `view-open-file.py` hook:
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

Open files in Vim using the `!` prefix:
- `! edit file.py` — opens Vim in a new split pane below
- `! edittab file.py` — opens Vim as a tab in the same pane

If you use Vim with `cmux-sync.vim`, broot's Enter key sends files to Vim via signal file IPC.

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

### Claude Code

Hooks are configured in `~/.claude/settings.json` — see [SETUP.md](SETUP.md).

### OpenCode

The `plugins/opencode/cmux-toolkit.ts` adapter translates OpenCode's plugin events (`tool.execute.after`, `chat.message`, `shell.env`, `event`) into the same JSON-on-stdin format the hook scripts expect. The plugin also injects `CMUX_SESSION_ID` into the shell environment for broot/Vim integration.

### Optional: auto Vim subpane

If you prefer Vim to open automatically on session start, add these SessionStart hooks to your Claude Code `settings.json`:

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
├── hooks/                      # Tool hooks (→ ~/.cmux-toolkit/hooks/ + ~/.claude/hooks/)
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
├── lib/                        # Shared config libraries
│   ├── common.sh               # Path constants for shell hooks
│   └── common.py               # Path constants for Python hooks
├── plugins/
│   └── opencode/
│       └── cmux-toolkit.ts     # OpenCode adapter plugin
├── config/
│   ├── cmux/
│   │   └── config.ghostty      # Dark theme + inactive pane dimming
│   ├── broot/                  # broot configuration
│   │   ├── conf.hjson
│   │   ├── verbs.hjson         # Enter key → open-file verb
│   │   └── skins/
│   └── vim/
│       └── cmux-sync.vim       # Vim signal file polling
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
- At least one AI coding tool:
  - [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
  - [OpenCode](https://opencode.ai)
- [Node.js](https://nodejs.org) + `marked` package (for Markdown rendering)
- `broot` and `jq` (installed automatically by setup.sh)

## Updating

```bash
git -C ~/cmux-toolkit pull && bash ~/cmux-toolkit/setup.sh
```

Symlinks point to the repo, so most updates are instant after `git pull`.
