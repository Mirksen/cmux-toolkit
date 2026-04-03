#!/bin/bash
# Claude Code SessionEnd hook: close all tracked view surfaces.
# Only fires on actual exit, not on /resume.

INPUT=$(cat)
eval "$(echo "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'SESSION_ID={d.get(\"session_id\",\"\")}')
print(f'REASON={d.get(\"reason\",\"\")}')
" 2>/dev/null)"

[[ -z "$SESSION_ID" ]] && exit 0
[[ "$REASON" == "resume" ]] && exit 0

TRACKING_FILE="$HOME/.claude/view-surfaces/${SESSION_ID}.txt"
[[ ! -f "$TRACKING_FILE" ]] && exit 0

# Close all tracked surfaces (verify they exist first)
TREE=$(cmux tree 2>/dev/null || true)

while IFS= read -r surface_ref; do
  [[ -z "$surface_ref" ]] && continue
  echo "$TREE" | grep -qF "$surface_ref" || continue
  cmux close-surface --surface "$surface_ref" 2>/dev/null || true
done < "$TRACKING_FILE"

# Clean up tracking file
rm -f "$TRACKING_FILE"

exit 0
