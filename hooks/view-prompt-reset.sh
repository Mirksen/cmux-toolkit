#!/bin/bash
# Claude Code UserPromptSubmit hook: reset changes view for new prompt cycle.
# Clears the changes log and navigates the browser tab to an empty state.

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
[[ -z "$SESSION_ID" ]] && exit 0

# Clear the changes log
rm -f "$HOME/.claude/view-changes/${SESSION_ID}.jsonl" 2>/dev/null

# Navigate existing browser tab to a blank "waiting" page
TRACKING_FILE="$HOME/.claude/view-surfaces/${SESSION_ID}.txt"
if [[ -f "$TRACKING_FILE" ]]; then
  SURFACE=$(tail -1 "$TRACKING_FILE" | tr -d '[:space:]')
  if [[ -n "$SURFACE" ]]; then
    BLANK="/tmp/view-changes-${SESSION_ID}.html"
    cat > "$BLANK" << 'ENDHTML'
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
:root { --bg: #fff; --fg: #86868b; }
@media (prefers-color-scheme: dark) { :root { --bg: #1e1e1e; --fg: #858585; } }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  display: flex; align-items: center; justify-content: center; height: 90vh;
  color: var(--fg); background: var(--bg); }
p { font-size: 1.1em; }
</style></head><body><p>Waiting for changes...</p></body></html>
ENDHTML
    cmux browser --surface "$SURFACE" navigate "file://$BLANK" 2>/dev/null || true
  fi
fi

exit 0
