#!/usr/bin/env bash
# Usage: ./speak.sh "Câu cần đọc."
# Env:
#   SPEAK_VOICE     primary voice (default: "Linh (Enhanced)" — falls back to Linh)
#   SPEAK_EN_VOICE  voice for English fragments when primary is Linh* (default: Samantha)
#   SPEAK_RATE      words per minute (default: 170 — natural, unhurried pace)
set -euo pipefail

TEXT="${1:?Usage: speak.sh \"text\"}"
VOICE="${SPEAK_VOICE:-Linh (Enhanced)}"
EN_VOICE="${SPEAK_EN_VOICE:-Samantha}"
RATE="${SPEAK_RATE:-170}"

# Graceful fallback: if requested voice isn't installed, drop to plain Linh.
# `say -v "?"` lines look like: `Linh (Enhanced)     vi_VN    # Xin chào!...`
# The sed strips the trailing ` <locale> # <comment>` so we can exact-match the name.
if ! say -v "?" | sed -E 's/[[:space:]]+[a-z]+_[A-Z]+[[:space:]]+#.*$//' | grep -qxF "$VOICE"; then
  echo "WARNING: voice '$VOICE' not installed; falling back to 'Linh'." >&2
  echo "         Cài Enhanced: System Settings → Accessibility → Spoken Content → Manage Voices → Vietnamese → Linh (Enhanced) → Download" >&2
  VOICE="Linh"
fi

# When primary voice is Linh (Vietnamese), text inside backticks is read by
# the English voice. Convention: callers wrap English words/phrases in
# backticks, e.g. "Hôm nay tôi có `meeting` về `deadline` mới."
if [[ "$VOICE" == Linh* ]]; then
  # Split on backticks: even-indexed parts are Vietnamese, odd-indexed are English.
  BT=$'\x60'
  IFS="$BT" read -ra PARTS <<< "$TEXT"
  for i in "${!PARTS[@]}"; do
    chunk="${PARTS[$i]}"
    # Trim leading/trailing whitespace
    chunk="${chunk#"${chunk%%[![:space:]]*}"}"
    chunk="${chunk%"${chunk##*[![:space:]]}"}"
    [[ -z "$chunk" ]] && continue
    if (( i % 2 == 1 )); then
      say -v "$EN_VOICE" -r "$RATE" "$chunk"
    else
      say -v "$VOICE" -r "$RATE" "$chunk"
    fi
  done
else
  say -v "$VOICE" -r "$RATE" "$TEXT"
fi
