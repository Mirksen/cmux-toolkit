#!/bin/bash
# Claude Code UserPromptSubmit hook: close old view tabs before new prompt.
# Reads tracked surface IDs and closes non-focused ones.

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
[[ -z "$SESSION_ID" ]] && exit 0

TRACKING_FILE="$HOME/.claude/view-surfaces/${SESSION_ID}.txt"
[[ ! -f "$TRACKING_FILE" ]] && exit 0

# Get currently focused/selected surfaces from cmux tree
FOCUSED=$(cmux tree 2>/dev/null | grep -E '\[selected\]|◀ active' | grep -o 'surface:[0-9]*' || true)

# Close each tracked surface unless it's focused
# First verify the surface exists in cmux tree to avoid closing random surfaces
TREE=$(cmux tree 2>/dev/null || true)

while IFS= read -r surface_ref; do
  [[ -z "$surface_ref" ]] && continue
  # Skip if surface doesn't exist in current tree
  echo "$TREE" | grep -qF "$surface_ref" || continue
  if echo "$FOCUSED" | grep -qF "$surface_ref"; then
    # Surface is focused — keep it
    continue
  fi
  cmux close-surface --surface "$surface_ref" 2>/dev/null || true
done < "$TRACKING_FILE"

# Clear tracking file
: > "$TRACKING_FILE"

exit 0
