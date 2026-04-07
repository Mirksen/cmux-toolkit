# cmux-toolkit shell init — sourced from .zshrc
# Provides: broot-toggle keybind (Opt+ArrowUp), ~/.local/bin in PATH

export PATH="$HOME/.local/bin:$PATH"

# broot sidebar toggle (requires broot --install)
if [[ -f "$HOME/.config/broot/launcher/bash/br" ]]; then
    source "$HOME/.config/broot/launcher/bash/br"
    broot-toggle() {
        BUFFER="br"
        zle accept-line
        zle reset-prompt
    }
    zle -N broot-toggle
    bindkey '\e[1;3A' broot-toggle
fi
