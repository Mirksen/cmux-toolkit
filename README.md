# cmux-toolkit

IDE-like pane management for Claude Code in [cmux](https://cmux.dev) — automatic Vim subpane and broot file browser sidebar.

## What you get

When you start Claude Code in cmux, the toolkit automatically creates:

```
┌─────────────┬──────────────────────┐
│             │                      │
│   broot     │    Claude Code       │
│   (files)   │                      │
│             ├──────────────────────┤
│  Opt+↑      │    Vim               │
│  to toggle  │    (auto-opens       │
│             │     edited files)    │
└─────────────┴──────────────────────┘
```

- **Vim subpane** — files Claude reads/edits/writes open here automatically in real-time
- **broot sidebar** — toggle with `Option + Arrow Up`, select files to open in Vim
- **Session-aware** — each Claude session has its own Vim instance, supports `/resume`

## Quick start

See [SETUP.md](SETUP.md) for the copy-paste instruction you give to Claude Code.

Or manually:

```bash
git clone https://github.com/Mirksen/cmux-toolkit.git ~/cmux-toolkit
bash ~/cmux-toolkit/setup.sh
```

Then add the hooks to your `~/.claude/settings.json` and the keybind to your `.zshrc` (see SETUP.md for details).

## How it works

### Signal file IPC

Claude Code hooks write file paths to `~/.vim/claude-open-file-{session_id}`. Vim polls this file every 200ms and opens new entries as buffers.

Special directives:
- `::reset::` — wipe buffers from previous prompt (sent on each new prompt)
- `::rebind::NEW_ID` — switch to new session (sent on `/resume`)
- `::quit::` — close Vim (sent on session exit)

### Hook architecture

```
SessionStart ─→ vim-pane-open-dispatch.sh ─→ cmux: vim-pane-open-cmux.sh
                                            iTerm2: vim-pane-open.sh
             ─→ broot-pane-open.sh ────────→ cmux: broot-pane-open-cmux.sh
                                            iTerm2: AppleScript

PostToolUse  ─→ vim-open-file.py ──────────→ appends path to signal file

SessionEnd   ─→ vim-pane-close.sh ─────────→ sends ::quit:: to signal file
             ─→ broot-pane-close.sh ────────→ cleans up marker files

Keybind      ─→ broot-pane-toggle-dispatch.sh → cmux: broot-pane-toggle-cmux.sh
  (Opt+↑)                                      iTerm2: broot-pane-toggle.sh
```

### Marker files

- `~/.claude/broot-pane-id` — cmux surface ref for broot pane
- `~/.claude/vim-panes/{surface}.ref` — cmux surface ref + session ID for Vim

## Structure

```
cmux-toolkit/
├── hooks/                  # Claude Code hook scripts
│   ├── vim-pane-*.sh       # Vim subpane lifecycle
│   ├── vim-open-file.py    # PostToolUse → signal file
│   ├── vim-prompt-reset.sh # Reset buffers on new prompt
│   ├── broot-pane-*.sh     # broot sidebar lifecycle
│   ├── broot-open-file.sh  # broot Enter → Vim IPC
│   └── fix-whitespace-escape.py  # iCloud path fix
├── config/
│   ├── broot/              # broot configuration
│   │   ├── conf.hjson
│   │   ├── verbs.hjson     # Enter key → open in Vim
│   │   └── skins/
│   └── vim/
│       └── claude-sync.vim # Vim signal file polling
├── setup.sh                # Idempotent setup script
├── SETUP.md                # Copy-paste instructions for Claude Code
└── README.md
```

## Requirements

- macOS with [Homebrew](https://brew.sh)
- [cmux](https://cmux.dev) terminal multiplexer
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- `broot` and `jq` (installed automatically by setup.sh)

## Updating

```bash
git -C ~/cmux-toolkit pull && bash ~/cmux-toolkit/setup.sh
```

Symlinks point to the repo, so most updates are instant after `git pull`.
