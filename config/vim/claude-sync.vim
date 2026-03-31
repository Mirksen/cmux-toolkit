" === Claude Code Sync ===
" Watches a session-specific signal file for paths written by Claude Code's
" PostToolUse hook and opens them automatically. Toggle with :ClaudeSync.
" Each Vim instance is bound to one Claude session via $CLAUDE_SESSION_ID.
"
" Usage: add `source ~/.vim/claude-sync.vim` to your .vimrc
" Requires: lightline.vim (for status bar updates)

let g:claude_sync_enabled = 1
let s:claude_session_id = $CLAUDE_SESSION_ID
let s:claude_signal = expand('~/.vim/claude-open-file-' . s:claude_session_id)
let s:claude_timer_id = -1
let s:claude_managed_bufs = []

function! s:ClaudeCheckFile(timer_id) abort
    if !g:claude_sync_enabled | return | endif
    if s:claude_session_id ==# '' | return | endif
    if !filereadable(s:claude_signal) | return | endif
    let l:lines = readfile(s:claude_signal)
    if empty(l:lines) || l:lines[0] ==# '' | return | endif

    " Clear signal file immediately to avoid re-opening
    call writefile([], s:claude_signal)

    " Process all lines — open each file as a buffer
    let g:claude_buffers = []
    let l:last_entry = ''
    for l:raw in l:lines
        let l:entry = trim(l:raw)
        if l:entry ==# '' | continue | endif

        " Quit signal from SessionEnd hook
        if l:entry ==# '::quit::'
            qa!
        endif

        " Rebind signal from /resume — switch to polling a new session's file
        if l:entry =~# '^::rebind::'
            let l:new_id = substitute(l:entry, '^::rebind::', '', '')
            if l:new_id !=# ''
                let s:claude_session_id = l:new_id
                let s:claude_signal = expand('~/.vim/claude-open-file-' . s:claude_session_id)
                call s:ClaudeWipeBuffers()
                echo '[Claude] Rebound to session: ' . l:new_id[:7]
            endif
            continue
        endif

        " Reset signal from UserPromptSubmit hook — wipe previous-prompt buffers
        if l:entry ==# '::reset::'
            call s:ClaudeWipeBuffers()
            continue
        endif

        " Support path:line format
        let l:parts = matchlist(l:entry, '^\(.\{-}\):\(\d\+\)$')
        if !empty(l:parts) && filereadable(l:parts[1])
            execute 'edit +' . l:parts[2] . ' ' . fnameescape(l:parts[1])
            call add(g:claude_buffers, fnamemodify(l:parts[1], ':t'))
            call s:ClaudeTrackBuf(bufnr('%'))
            let l:last_entry = l:entry
        elseif filereadable(l:entry)
            execute 'edit ' . fnameescape(l:entry)
            call add(g:claude_buffers, fnamemodify(l:entry, ':t'))
            call s:ClaudeTrackBuf(bufnr('%'))
            let l:last_entry = l:entry
        endif
    endfor

    if l:last_entry !=# ''
        if exists('*lightline#update')
            call lightline#update()
        endif
        redraw
    endif
endfunction

function! s:ClaudeTrackBuf(bufnr) abort
    if index(s:claude_managed_bufs, a:bufnr) == -1
        call add(s:claude_managed_bufs, a:bufnr)
    endif
endfunction

function! s:ClaudeWipeBuffers() abort
    for l:bnr in s:claude_managed_bufs
        if bufexists(l:bnr) && !getbufvar(l:bnr, '&modified')
            try
                execute 'bwipeout ' . l:bnr
            catch
            endtry
        endif
    endfor
    let s:claude_managed_bufs = []
    let g:claude_buffers = []
endfunction

function! s:ClaudeSyncToggle() abort
    let g:claude_sync_enabled = !g:claude_sync_enabled
    if g:claude_sync_enabled
        echo '[Claude] Sync ON (session: ' . s:claude_session_id[:7] . ')'
    else
        echo '[Claude] Sync OFF'
    endif
endfunction

command! ClaudeSync call s:ClaudeSyncToggle()

" Start polling timer (200ms) — only if bound to a session
if has('timers') && s:claude_session_id !=# ''
    let s:claude_timer_id = timer_start(200, function('s:ClaudeCheckFile'), {'repeat': -1})
endif
