#!/bin/bash
# cmux-toolkit setup: installs broot + vim subpane integration for cmux
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

# ── 1. Check/install brew dependencies ──
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

# ── 2. Create runtime directories ──
info "Creating directories..."
mkdir -p ~/.claude/hooks ~/.claude/broot-panes ~/.claude/vim-panes ~/.vim ~/.config/broot/skins

# ── 3. Fix broot verbs.hjson — replace __HOME__ placeholder with actual $HOME ──
info "Preparing broot config..."
VERBS_COPY="$REPO_DIR/config/broot/verbs.hjson"
if grep -q '__HOME__' "$VERBS_COPY" 2>/dev/null; then
    sed -i '' "s|__HOME__|$HOME|g" "$VERBS_COPY"
    info "Replaced __HOME__ placeholder in verbs.hjson with $HOME"
fi

# ── 4. Symlink hook scripts ──
info "Linking hook scripts..."
for hook in "$REPO_DIR"/hooks/*; do
    name=$(basename "$hook")
    backup_and_link "$hook" "$HOME/.claude/hooks/$name"
done

# ── 5. Symlink broot config ──
info "Linking broot config..."
backup_and_link "$REPO_DIR/config/broot/conf.hjson" "$HOME/.config/broot/conf.hjson"
backup_and_link "$REPO_DIR/config/broot/verbs.hjson" "$HOME/.config/broot/verbs.hjson"
backup_and_link "$REPO_DIR/config/broot/skins/skin-p10k.hjson" "$HOME/.config/broot/skins/skin-p10k.hjson"

# ── 6. Handle Vim config ──
info "Setting up Vim integration..."
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

# ── 7. Install vim-plug if needed ──
if [[ ! -f "$HOME/.vim/autoload/plug.vim" ]]; then
    info "Installing vim-plug..."
    curl -fLo "$HOME/.vim/autoload/plug.vim" --create-dirs \
        https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim 2>/dev/null
    info "vim-plug installed"
fi

# ── 8. Run broot --install (creates shell launcher) ──
if [[ ! -f "$HOME/.config/broot/launcher/bash/br" ]]; then
    info "Running broot --install..."
    broot --install 2>/dev/null || true
fi

# ── Summary ──
echo ""
info "Setup complete!"
echo ""
echo "  Hooks:  ~/.claude/hooks/ ($(ls ~/.claude/hooks/*.sh ~/.claude/hooks/*.py 2>/dev/null | wc -l | tr -d ' ') files)"
echo "  Broot:  ~/.config/broot/ (conf.hjson, verbs.hjson, skin)"
echo "  Vim:    ~/.vim/claude-sync.vim (sourced from .vimrc)"
echo ""
warn "Remaining manual steps (let Claude Code handle these):"
echo "  1. Add broot-toggle keybind to .zshrc"
echo "  2. Merge hooks into ~/.claude/settings.json"
echo "  3. Run: source ~/.zshrc"
