" === cmux-toolkit Sync ===
" Watches a session-specific signal file for paths written by AI coding
" tool hooks (Claude Code, OpenCode, etc.) and opens them automatically.
" Toggle with :CmuxSync.
" Each Vim instance is bound to one session via $CMUX_SESSION_ID.
"
" Usage: add `source ~/.vim/cmux-sync.vim` to your .vimrc
" Requires: lightline.vim (for status bar updates)

let g:cmux_sync_enabled = 1
let s:cmux_session_id = $CMUX_SESSION_ID
let s:cmux_signal = expand('~/.vim/cmux-open-file-' . s:cmux_session_id)
let s:cmux_timer_id = -1
let s:cmux_managed_bufs = []

function! s:CmuxCheckFile(timer_id) abort
    if !g:cmux_sync_enabled | return | endif
    if s:cmux_session_id ==# '' | return | endif
    if !filereadable(s:cmux_signal) | return | endif
    let l:lines = readfile(s:cmux_signal)
    if empty(l:lines) || l:lines[0] ==# '' | return | endif

    " Clear signal file immediately to avoid re-opening
    call writefile([], s:cmux_signal)

    " Process all lines — open each file as a buffer
    let g:cmux_buffers = []
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
                let s:cmux_session_id = l:new_id
                let s:cmux_signal = expand('~/.vim/cmux-open-file-' . s:cmux_session_id)
                call s:CmuxWipeBuffers()
                echo '[cmux] Rebound to session: ' . l:new_id[:7]
            endif
            continue
        endif

        " Reset signal from UserPromptSubmit hook — wipe previous-prompt buffers
        if l:entry ==# '::reset::'
            call s:CmuxWipeBuffers()
            continue
        endif

        " Support path:line format
        let l:parts = matchlist(l:entry, '^\(.\{-}\):\(\d\+\)$')
        if !empty(l:parts) && filereadable(l:parts[1])
            execute 'edit +' . l:parts[2] . ' ' . fnameescape(l:parts[1])
            call add(g:cmux_buffers, fnamemodify(l:parts[1], ':t'))
            call s:CmuxTrackBuf(bufnr('%'))
            let l:last_entry = l:entry
        elseif filereadable(l:entry)
            execute 'edit ' . fnameescape(l:entry)
            call add(g:cmux_buffers, fnamemodify(l:entry, ':t'))
            call s:CmuxTrackBuf(bufnr('%'))
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

function! s:CmuxTrackBuf(bufnr) abort
    if index(s:cmux_managed_bufs, a:bufnr) == -1
        call add(s:cmux_managed_bufs, a:bufnr)
    endif
endfunction

function! s:CmuxWipeBuffers() abort
    for l:bnr in s:cmux_managed_bufs
        if bufexists(l:bnr) && !getbufvar(l:bnr, '&modified')
            try
                execute 'bwipeout ' . l:bnr
            catch
            endtry
        endif
    endfor
    let s:cmux_managed_bufs = []
    let g:cmux_buffers = []
endfunction

function! s:CmuxSyncToggle() abort
    let g:cmux_sync_enabled = !g:cmux_sync_enabled
    if g:cmux_sync_enabled
        echo '[cmux] Sync ON (session: ' . s:cmux_session_id[:7] . ')'
    else
        echo '[cmux] Sync OFF'
    endif
endfunction

command! CmuxSync call s:CmuxSyncToggle()
" Backward compat alias
command! ClaudeSync call s:CmuxSyncToggle()

" Start polling timer (200ms) — only if bound to a session
if has('timers') && s:cmux_session_id !=# ''
    let s:cmux_timer_id = timer_start(200, function('s:CmuxCheckFile'), {'repeat': -1})
endif
