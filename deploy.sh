#!/usr/bin/env bash
# Deploy ppread skill source files to the Claude Code skills directory.
# Source of truth lives here; this copies the deployable files to ~/.claude/skills/ppread/.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/ppread"

mkdir -p "$DEST"
install -m 0644 "$SRC/SKILL.md"          "$DEST/SKILL.md"
install -m 0644 "$SRC/lecture-format.md" "$DEST/lecture-format.md"
install -m 0755 "$SRC/fetch.py"          "$DEST/fetch.py"

echo "deployed -> $DEST"
