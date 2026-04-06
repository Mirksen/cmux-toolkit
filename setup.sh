#!/bin/bash
# cmux-toolkit setup: viewtab browser tabs, manual Vim/edit, on-demand broot
# Supports: Claude Code, OpenCode (and any future tool with compatible hooks)
# Idempotent — safe to re-run after updates (git pull && bash setup.sh)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[x]${NC} $*"; }

backup_and_link() {
    local src="$1" dst="$2"
    if [[ -L "$dst" ]]; then
        local target
        target=$(readlink "$dst")
        if [[ "$target" == "$src" ]]; then
            return 0  # already correct
        fi
        rm "$dst"
    elif [[ -e "$dst" ]]; then
        mv "$dst" "${dst}.bak"
        warn "Backed up existing $(basename "$dst") → ${dst}.bak"
    fi
    ln -sf "$src" "$dst"
    info "Linked $(basename "$dst")"
}

# ── 1. Check/install dependencies ──
info "Checking dependencies..."
for pkg in broot jq; do
    if ! command -v "$pkg" &>/dev/null; then
        if command -v brew &>/dev/null; then
            info "Installing $pkg via brew..."
            BUFFER="br"
    zle accept-lineew install "$pkg"
        else
            err "$pkg not found and brew not available. Install $pkg manually."
            exit 1
        fi
    fi
done

if ! command -v node &>/dev/null; then
    warn "Node.js not found — Markdown rendering in viewtab requires Node.js."
    warn "Install Node.js: brew install node"
else
    # Ensure marked is available globally (CLI is broken in v17, but API works via NODE_PATH)
    if ! node -e "require('marked')" 2>/dev/null; then
        NODE_PATH="$(npm root -g 2>/dev/null)" node -e "require('marked')" 2>/dev/null || {
            info "Installing marked globally for Markdown rendering..."
            npm install -g marked
        }
    fi
fi

# ── 2. Create runtime directories ──
info "Creating directories..."
mkdir -p ~/.cmux-toolkit/hooks ~/.cmux-toolkit/broot-panes ~/.cmux-toolkit/vim-panes \
         ~/.cmux-toolkit/view-surfaces ~/.cmux-toolkit/view-changes \
         ~/.claude/hooks ~/.vim ~/.config/broot/skins ~/.local/bin

# ── 3. Prepare broot verbs.hjson — copy to config dir with __HOME__ resolved ──
info "Preparing broot config..."
VERBS_SRC="$REPO_DIR/config/broot/verbs.hjson"
VERBS_DST="$HOME/.config/broot/verbs.hjson"
if [[ -f "$VERBS_SRC" ]]; then
    # Remove existing symlink/file before copying (cp fails if dst symlinks to src)
    rm -f "$VERBS_DST"
    cp "$VERBS_SRC" "$VERBS_DST"
    sed -i '' "s|__HOME__|$HOME|g" "$VERBS_DST"
    info "Installed verbs.hjson with \$HOME resolved"
fi

# ── 4. Symlink hook scripts ──
info "Linking hook scripts..."
for hook in "$REPO_DIR"/hooks/*.sh "$REPO_DIR"/hooks/*.py; do
    [[ -f "$hook" ]] || continue
    name=$(basename "$hook")
    # Claude Code hooks (settings.json references these)
    backup_and_link "$hook" "$HOME/.claude/hooks/$name"
    # Tool-agnostic hooks (broot, OpenCode reference these)
    backup_and_link "$hook" "$HOME/.cmux-toolkit/hooks/$name"
done
# Templates are resolved via os.path.realpath(__file__) in hooks, no symlink needed

# ── 5. Symlink bin/ commands ──
info "Linking bin/ commands..."
for cmd in view edit render-md; do
    backup_and_link "$REPO_DIR/bin/$cmd" "$HOME/.local/bin/$cmd"
done
# Symlinks for tab-mode aliases (these are symlinks in the repo: viewtab→view, edittab→edit)
for cmd in viewtab edittab; do
    backup_and_link "$REPO_DIR/bin/$cmd" "$HOME/.local/bin/$cmd"
done

# ── 6. Symlink broot config (verbs.hjson is copied in step 3, not symlinked) ──
info "Linking broot config..."
backup_and_link "$REPO_DIR/config/broot/conf.hjson" "$HOME/.config/broot/conf.hjson"
backup_and_link "$REPO_DIR/config/broot/skins/skin-p10k.hjson" "$HOME/.config/broot/skins/skin-p10k.hjson"

# ── 7. Symlink cmux Ghostty config (dark theme + dimming) ──
info "Linking cmux theme..."
CMUX_CONFIG_DIR="$HOME/Library/Application Support/com.cmuxterm.app"
if [[ -d "$CMUX_CONFIG_DIR" ]]; then
    backup_and_link "$REPO_DIR/config/cmux/config.ghostty" "$CMUX_CONFIG_DIR/config.ghostty"
else
    warn "cmux config dir not found — skipping theme. Install cmux first, then re-run setup."
fi

# ── 8. Handle Vim config ──
info "Setting up Vim integration..."
CMUX_SYNC="$REPO_DIR/config/vim/cmux-sync.vim"
backup_and_link "$CMUX_SYNC" "$HOME/.vim/cmux-sync.vim"
# Keep old name as symlink for backward compat
backup_and_link "$CMUX_SYNC" "$HOME/.vim/claude-sync.vim"

if [[ -f "$HOME/.vimrc" ]]; then
    # Migrate from old claude-sync.vim to cmux-sync.vim
    if grep -q 'claude-sync.vim' "$HOME/.vimrc" 2>/dev/null; then
        sed -i '' 's|source ~/.vim/claude-sync.vim|source ~/.vim/cmux-sync.vim|g' "$HOME/.vimrc"
        sed -i '' 's|Claude Code file sync|cmux-toolkit file sync|g' "$HOME/.vimrc"
        info "Migrated .vimrc from claude-sync.vim to cmux-sync.vim"
    elif ! grep -q 'cmux-sync.vim' "$HOME/.vimrc" 2>/dev/null; then
        echo '' >> "$HOME/.vimrc"
        echo '" cmux-toolkit file sync (added by cmux-toolkit)' >> "$HOME/.vimrc"
        echo 'source ~/.vim/cmux-sync.vim' >> "$HOME/.vimrc"
        info "Added source line to existing .vimrc"
    else
        info ".vimrc already sources cmux-sync.vim"
    fi
else
    echo '" cmux-toolkit file sync' > "$HOME/.vimrc"
    echo 'source ~/.vim/cmux-sync.vim' >> "$HOME/.vimrc"
    info "Created minimal .vimrc with cmux-sync"
fi

# ── 9. Install vim-plug if needed ──
if [[ ! -f "$HOME/.vim/autoload/plug.vim" ]]; then
    info "Installing vim-plug..."
    curl -fLo "$HOME/.vim/autoload/plug.vim" --create-dirs \
        https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim 2>/dev/null
    info "vim-plug installed"
fi

# ── 10. Run broot --install (creates shell launcher) ──
if [[ ! -f "$HOME/.config/broot/launcher/bash/br" ]]; then
    info "Running broot --install..."
    BUFFER="br"
    zle accept-lineoot --install 2>/dev/null || true
fi

# ── 11. Claude Code settings.json — auto-merge hooks ──
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
info "Configuring Claude Code hooks..."
CMUX_HOOKS='{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/view-prompt-reset.sh"}]}],"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"python3 ~/.claude/hooks/fix-whitespace-escape.py"}]}],"PostToolUse":[{"matcher":"Edit|Write","hooks":[{"type":"command","command":"python3 ~/.claude/hooks/view-open-file.py"}]}],"SessionEnd":[{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/session-cleanup.sh"}]}]}'

if [[ -f "$CLAUDE_SETTINGS" ]]; then
    # Merge hooks into existing settings (preserves all other keys)
    MERGED=$(jq --argjson hooks "$CMUX_HOOKS" '.hooks = ($hooks * (.hooks // {}))' "$CLAUDE_SETTINGS" 2>/dev/null)
    if [[ -n "$MERGED" ]]; then
        echo "$MERGED" > "$CLAUDE_SETTINGS"
        info "Merged cmux-toolkit hooks into settings.json"
    else
        warn "Could not parse settings.json — merge hooks manually (see SETUP.md)"
    fi
else
    mkdir -p "$HOME/.claude"
    jq -n --argjson hooks "$CMUX_HOOKS" '{"hooks": $hooks}' > "$CLAUDE_SETTINGS"
    info "Created settings.json with cmux-toolkit hooks"
fi

# ── 12. .zshrc — auto-add broot keybind and PATH ──
info "Configuring .zshrc..."
if [[ -f "$HOME/.zshrc" ]]; then
    # Migrate old broot-toggle pointing to ~/.claude/hooks/
    if grep -q 'claude/hooks/broot-pane' "$HOME/.zshrc" 2>/dev/null; then
        sed -i '' 's|~/.claude/hooks/broot-pane.sh|~/.cmux-toolkit/hooks/broot-pane.sh|g' "$HOME/.zshrc"
        info "Migrated broot-toggle to ~/.cmux-toolkit/ path"
    fi

    # Add broot-toggle if not present
    if ! grep -q 'broot-toggle' "$HOME/.zshrc" 2>/dev/null; then
        cat >> "$HOME/.zshrc" << 'ZSHBLOCK'

# === broot sidebar toggle (Opt+ArrowUp) — added by cmux-toolkit ===
source "$HOME/.config/broot/launcher/bash/br"
broot-toggle() {
    BUFFER="br"
    zle accept-line
    zle reset-prompt
}
zle -N broot-toggle
bindkey '\e[1;3A' broot-toggle
ZSHBLOCK
        info "Added broot-toggle keybind to .zshrc"
    else
        info ".zshrc already has broot-toggle"
    fi

    # Add ~/.local/bin to PATH if not present
    if ! grep -q 'local/bin' "$HOME/.zshrc" 2>/dev/null; then
        echo '' >> "$HOME/.zshrc"
        echo '# Added by cmux-toolkit' >> "$HOME/.zshrc"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
        info "Added ~/.local/bin to PATH in .zshrc"
    else
        info ".zshrc already has ~/.local/bin in PATH"
    fi
else
    cat > "$HOME/.zshrc" << 'ZSHBLOCK'
export PATH="$HOME/.local/bin:$PATH"

# === broot sidebar toggle (Opt+ArrowUp) — added by cmux-toolkit ===
source "$HOME/.config/broot/launcher/bash/br"
broot-toggle() {
    BUFFER="br"
    zle accept-line
    zle reset-prompt
}
zle -N broot-toggle
bindkey '\e[1;3A' broot-toggle
ZSHBLOCK
    info "Created .zshrc with PATH and broot-toggle"
fi

# ── 13. OpenCode plugin setup ──
if command -v opencode &>/dev/null; then
    info "OpenCode detected — setting up plugin..."
    OPENCODE_PLUGINS="$HOME/.config/opencode/plugins"
    mkdir -p "$OPENCODE_PLUGINS"
    # OpenCode scans plugins/*.{ts,js} — must symlink the file, not the directory
    backup_and_link "$REPO_DIR/plugins/opencode/cmux-toolkit.ts" "$OPENCODE_PLUGINS/cmux-toolkit.ts"
    info "OpenCode plugin linked to $OPENCODE_PLUGINS/cmux-toolkit.ts"
else
    info "OpenCode not found — skipping plugin setup. Re-run setup after installing OpenCode."
fi

# ── Summary ──
echo ""
info "Setup complete!"
echo ""
echo "  State:    ~/.cmux-toolkit/ (view-changes, view-surfaces, vim-panes, broot-panes)"
echo "  Hooks:    ~/.cmux-toolkit/hooks/ + ~/.claude/hooks/ ($(ls ~/.cmux-toolkit/hooks/*.sh ~/.cmux-toolkit/hooks/*.py 2>/dev/null | wc -l | tr -d ' ') files)"
echo "  Commands: ~/.local/bin/{view,viewtab,edit,edittab,render-md}"
echo "  Theme:    ~/Library/Application Support/com.cmuxterm.app/config.ghostty"
echo "  Broot:    ~/.config/broot/ (conf.hjson, verbs.hjson, skin)"
echo "  Vim:      ~/.vim/cmux-sync.vim"
if command -v opencode &>/dev/null; then
    echo "  OpenCode: ~/.config/opencode/plugins/cmux-toolkit"
fi
echo ""
echo "  Supported tools: Claude Code, OpenCode"
echo ""
info "Run: source ~/.zshrc  (to activate in current shell)"
