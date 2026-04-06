#!/bin/bash
# cmux-toolkit setup: viewtab browser tabs, manual Vim/edit, on-demand broot
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
            brew install "$pkg"
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
mkdir -p ~/.claude/hooks ~/.claude/broot-panes ~/.claude/vim-panes ~/.claude/view-surfaces ~/.claude/view-changes ~/.vim ~/.config/broot/skins ~/.local/bin

# ── 3. Fix broot verbs.hjson — replace __HOME__ placeholder with actual $HOME ──
info "Preparing broot config..."
VERBS_COPY="$REPO_DIR/config/broot/verbs.hjson"
if grep -q '__HOME__' "$VERBS_COPY" 2>/dev/null; then
    sed -i '' "s|__HOME__|$HOME|g" "$VERBS_COPY"
    info "Replaced __HOME__ placeholder in verbs.hjson with $HOME"
fi

# ── 4. Symlink hook scripts (only .sh and .py, skip subdirectories) ──
info "Linking hook scripts..."
for hook in "$REPO_DIR"/hooks/*.sh "$REPO_DIR"/hooks/*.py; do
    [[ -f "$hook" ]] || continue
    name=$(basename "$hook")
    backup_and_link "$hook" "$HOME/.claude/hooks/$name"
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

# ── 6. Symlink broot config ──
info "Linking broot config..."
backup_and_link "$REPO_DIR/config/broot/conf.hjson" "$HOME/.config/broot/conf.hjson"
backup_and_link "$REPO_DIR/config/broot/verbs.hjson" "$HOME/.config/broot/verbs.hjson"
backup_and_link "$REPO_DIR/config/broot/skins/skin-p10k.hjson" "$HOME/.config/broot/skins/skin-p10k.hjson"

# ── 7. Symlink cmux Ghostty config (dark theme + dimming) ──
info "Linking cmux theme..."
CMUX_CONFIG_DIR="$HOME/Library/Application Support/com.cmuxterm.app"
if [[ -d "$CMUX_CONFIG_DIR" ]]; then
    backup_and_link "$REPO_DIR/config/cmux/config.ghostty" "$CMUX_CONFIG_DIR/config.ghostty"
else
    warn "cmux config dir not found — skipping theme. Install cmux first, then re-run setup."
fi

# ── 8. Handle Vim config (for manual edit/edittab) ──
info "Setting up Vim integration (for edit/edittab)..."
CLAUDE_SYNC="$REPO_DIR/config/vim/claude-sync.vim"
backup_and_link "$CLAUDE_SYNC" "$HOME/.vim/claude-sync.vim"

if [[ -f "$HOME/.vimrc" ]]; then
    if ! grep -q 'claude-sync.vim' "$HOME/.vimrc" 2>/dev/null; then
        echo '' >> "$HOME/.vimrc"
        echo '" Claude Code file sync (added by cmux-toolkit)' >> "$HOME/.vimrc"
        echo 'source ~/.vim/claude-sync.vim' >> "$HOME/.vimrc"
        info "Added source line to existing .vimrc"
    else
        info ".vimrc already sources claude-sync.vim"
    fi
else
    echo '" Claude Code file sync' > "$HOME/.vimrc"
    echo 'source ~/.vim/claude-sync.vim' >> "$HOME/.vimrc"
    info "Created minimal .vimrc with claude-sync"
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
    broot --install 2>/dev/null || true
fi

# ── Summary ──
echo ""
info "Setup complete!"
echo ""
echo "  Hooks:    ~/.claude/hooks/ ($(ls ~/.claude/hooks/*.sh ~/.claude/hooks/*.py 2>/dev/null | wc -l | tr -d ' ') files)"
echo "  Commands: ~/.local/bin/{view,viewtab,edit,edittab,render-md}"
echo "  Theme:    ~/Library/Application Support/com.cmuxterm.app/config.ghostty"
echo "  Broot:    ~/.config/broot/ (conf.hjson, verbs.hjson, skin)"
echo "  Vim:      ~/.vim/claude-sync.vim (for manual edit/edittab)"
echo ""
warn "Remaining manual steps (let Claude Code handle these):"
echo "  1. Add broot-toggle keybind to .zshrc"
echo "  2. Merge hooks into ~/.claude/settings.json"
echo "  3. Ensure ~/.local/bin is in PATH"
echo "  4. Run: source ~/.zshrc"
