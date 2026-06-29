#!/usr/bin/env bash
# =============================================================================
# quicknotes SessionStart hook — prints a one-line reminder summary.
#
# Replaces session_reminder.py. Bash startup is ~5ms vs Python's ~400ms.
# ALWAYS exits 0 — never blocks the session, even if the notes store is
# missing, malformed, or on fire.
# =============================================================================
set -euo pipefail

NOTES_DIR="${QUICKNOTES_HOME:-$HOME/.quicknotes}/notes"

# Silently exit if no notes directory exists yet
[ -d "$NOTES_DIR" ] || exit 0

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CWD=$(pwd)

# Detect current project (best-effort, never fails)
PROJECT=$(git -C "$CWD" remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||' || true)
[ -z "$PROJECT" ] && PROJECT=$(basename "$CWD")

due_count=0
here_count=0
due_titles=()

# Scan all note files
for f in "$NOTES_DIR"/*.md; do
  [ -f "$f" ] || continue

  # --- Extract due date ---
  due_val=$(grep -m1 '^due:' "$f" 2>/dev/null | \
    sed -n 's/^due:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p' | \
    sed 's/,[[:space:]]*$//' | xargs || true)
  if [ -n "$due_val" ] && [ "$due_val" != "null" ] && [[ "$due_val" < "$NOW" ]]; then
    due_count=$((due_count + 1))
    # Extract title for display
    title=$(grep -m1 '^title:' "$f" 2>/dev/null | \
      sed -n 's/^title:[[:space:]]*"\([^"]*\)".*/\1/p' || echo "(untitled)")
    [ -n "$title" ] && due_titles+=("$title")
  fi

  # --- Check "here" match ---
  proj_val=$(grep -m1 '^project:' "$f" 2>/dev/null | \
    sed -n 's/^project:[[:space:]]*"\([^"]*\)".*/\1/p' || true)
  cwd_val=$(grep -m1 '^cwd:' "$f" 2>/dev/null | \
    sed -n 's/^cwd:[[:space:]]*"\([^"]*\)".*/\1/p' || true)

  if [ "$proj_val" = "$PROJECT" ] || [ "$cwd_val" = "$CWD" ]; then
    here_count=$((here_count + 1))
  fi
done

# Build status message
bits=""
[ "$due_count" -gt 0 ] && bits="$due_count due"
if [ "$here_count" -gt 0 ]; then
  if [ -n "$bits" ]; then
    bits="$bits, $here_count open for this project"
  else
    bits="$here_count open for this project"
  fi
fi

# Print summary if there's anything to report
if [ -n "$bits" ]; then
  echo "📝 quicknotes: $bits  (run \`qn due\` / \`qn here\`)"
  for title in "${due_titles[@]:0:5}"; do
    echo "   • due: $title"
  done
fi

exit 0
