#!/usr/bin/env bash
# Installer for the "end-session" Claude Code skill — בין קודש לקלוד.
# Usage:  curl -L https://hiyabh.github.io/claude-end-session-skill/install.sh | bash
set -euo pipefail

BUNDLE_URL="https://hiyabh.github.io/claude-end-session-skill/end-session-skill.tar.gz"
SKILLS_DIR="${HOME}/.claude/skills"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Installing the 'end-session' skill into: $SKILLS_DIR"
mkdir -p "$SKILLS_DIR"

echo "==> Downloading bundle..."
if command -v curl >/dev/null 2>&1; then
  curl -fL -o "$TMP/bundle.tar.gz" "$BUNDLE_URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$TMP/bundle.tar.gz" "$BUNDLE_URL"
else
  echo "ERROR: need curl or wget." >&2; exit 1
fi

echo "==> Extracting..."
mkdir -p "$TMP/x"
tar -xzf "$TMP/bundle.tar.gz" -C "$TMP/x"
SRC="$TMP/x/skills"
[ -d "$SRC" ] || SRC="$(find "$TMP/x" -maxdepth 2 -type d -name skills | head -n1)"

dest="$SKILLS_DIR/end-session"
if [ -e "$dest" ]; then
  echo "   skip (already exists): end-session — remove it first to reinstall."
else
  cp -r "$SRC/end-session" "$dest"
  echo "   installed: end-session"
fi

echo ""
echo "==> Done. Restart Claude Code so it picks up the new skill."
echo "==> Use it by typing 'סיימנו' or /end-session at the end of a work session."
