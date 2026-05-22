#!/usr/bin/env bash
# Usage: ./speak.sh "Câu tiếng Việt cần đọc."
# Env:
#   SPEAK_VOICE  macOS voice name (default: "Linh (Enhanced)" — falls back to Linh if not installed)
#   SPEAK_RATE   words per minute (default: 265 — ~1.5x Linh's natural pace)
set -euo pipefail

TEXT="${1:?Usage: speak.sh \"text\"}"
VOICE="${SPEAK_VOICE:-Linh (Enhanced)}"
RATE="${SPEAK_RATE:-265}"

# Graceful fallback: if requested voice isn't installed, drop to plain Linh.
# `say -v "?"` lines look like: `Linh (Enhanced)     vi_VN    # Xin chào!...`
# The sed strips the trailing ` <locale> # <comment>` so we can exact-match the name.
if ! say -v "?" | sed -E 's/[[:space:]]+[a-z]+_[A-Z]+[[:space:]]+#.*$//' | grep -qxF "$VOICE"; then
  echo "WARNING: voice '$VOICE' not installed; falling back to 'Linh'." >&2
  echo "         Cài Enhanced: System Settings → Accessibility → Spoken Content → Manage Voices → Vietnamese → Linh (Enhanced) → Download" >&2
  VOICE="Linh"
fi

say -v "$VOICE" -r "$RATE" "$TEXT"
