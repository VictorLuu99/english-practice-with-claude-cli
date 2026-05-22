#!/usr/bin/env bash
# Usage: ./speak.sh "Câu tiếng Việt cần đọc."
# Env:
#   SPEAK_VOICE  macOS voice name (default: Linh)
#   SPEAK_RATE   words per minute (default: 175)
set -euo pipefail

TEXT="${1:?Usage: speak.sh \"text\"}"
VOICE="${SPEAK_VOICE:-Linh}"
RATE="${SPEAK_RATE:-175}"

say -v "$VOICE" -r "$RATE" "$TEXT"
