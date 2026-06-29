#!/usr/bin/env bash
# =============================================================================
# Opt-in installer for the `qn` shell alias.
#
# Adds a qn() function to your shell RC file so you can use `qn <text>` from
# any terminal prompt. The function delegates to Claude Code's slash command.
#
# Usage:  bash install_alias.sh [--yes]
#   --yes   Skip confirmation prompt
#
# Idempotent — safe to run multiple times.
# =============================================================================
set -euo pipefail

MARKER="# quicknotes qn() alias"
ASSUME_YES="${1:-}"

# Detect shell RC file
case "${SHELL##*/}" in
  zsh)  RC="$HOME/.zshrc" ;;
  bash) RC="$HOME/.bashrc" ;;
  *)    RC="${ZDOTDIR:-$HOME}/.profile" ;;
esac

read -r -d '' SNIPPET <<'ENDOFSNIPPET' || true
# quicknotes qn() alias
qn() {
  if [ $# -eq 0 ]; then
    echo "Usage: qn <note text>        capture a quick note"
    echo "       qn list                list all notes"
    echo "       qn search <query>      search notes"
    echo "       qn show <id>           show full note"
    echo "       qn done <id>           complete/delete a note"
    echo "       qn due                 show past-due notes"
    echo "       qn here                notes for this project"
    return 0
  fi
  claude --slash-command "qn $*"
}
ENDOFSNIPPET

# Check if already installed
if [ -f "$RC" ] && grep -qF "$MARKER" "$RC" 2>/dev/null; then
  echo "✓ qn alias already present in $RC — nothing to do."
  exit 0
fi

# Show what will be appended
echo "Will append the following to $RC:"
echo "----------------------------------------"
echo "$SNIPPET"
echo "----------------------------------------"

# Confirm unless --yes
if [ "$ASSUME_YES" != "--yes" ]; then
  printf "Proceed? [y/N] "
  read -r reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *) echo "Aborted — no changes made."; exit 0 ;;
  esac
fi

printf '\n%s\n' "$SNIPPET" >> "$RC"
echo "✓ Added qn() to $RC. Open a new shell or run: source $RC"
