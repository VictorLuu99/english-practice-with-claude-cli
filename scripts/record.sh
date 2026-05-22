#!/usr/bin/env bash
# Record from default mic until silence detected, then transcribe English with Whisper.
# Output (stdout): transcript text (may be empty if no speech).
# Stderr: progress messages.
#
# Env:
#   WHISPER_MODEL        path to ggml model (default: ~/.cache/whisper-cpp/ggml-small.en.bin)
#   RECORD_MAX_SECONDS   safety cap on recording length (default: 15)
#   SILENCE_TAIL         seconds of silence before stop (default: 1.5)
#   SILENCE_THRESHOLD    sox silence threshold (default: 3%)
set -euo pipefail

MODEL="${WHISPER_MODEL:-$HOME/.cache/whisper-cpp/ggml-small.en.bin}"
MAX_SECONDS="${RECORD_MAX_SECONDS:-15}"
SILENCE_TAIL="${SILENCE_TAIL:-1.5}"
SILENCE_THRESHOLD="${SILENCE_THRESHOLD:-3%}"

if [[ ! -f "$MODEL" ]]; then
  echo "ERROR: Whisper model not found at: $MODEL" >&2
  echo "Run ./scripts/setup.sh first." >&2
  exit 1
fi

if ! command -v rec >/dev/null 2>&1; then
  echo "ERROR: 'rec' (from sox) not found. Run ./scripts/setup.sh." >&2
  exit 1
fi

if ! command -v whisper-cli >/dev/null 2>&1; then
  echo "ERROR: 'whisper-cli' not found. Run ./scripts/setup.sh." >&2
  exit 1
fi

TMPBASE="$(mktemp -t engprac)"
TMPWAV="$TMPBASE.wav"
trap 'rm -f "$TMPBASE" "$TMPWAV" "$TMPWAV.out.txt"' EXIT

echo "🎤 Đang nghe... (nói xong giữ im ${SILENCE_TAIL}s, hoặc Ctrl-C)" >&2

# 16kHz mono is Whisper's expected input.
# silence args: start-detect=1 (immediate), 0.1s above thresh; stop-detect=1, ${SILENCE_TAIL}s below thresh.
rec -q -r 16000 -c 1 "$TMPWAV" \
    silence 1 0.1 "$SILENCE_THRESHOLD" 1 "$SILENCE_TAIL" "$SILENCE_THRESHOLD" \
    trim 0 "$MAX_SECONDS" 2>/dev/null || true

if [[ ! -s "$TMPWAV" ]]; then
  # No audio captured (e.g., user immediately silent and sox cut at start)
  echo ""
  exit 0
fi

# -nt: no timestamps. -otxt + -of: write transcript to ${TMPWAV}.out.txt
whisper-cli -m "$MODEL" -f "$TMPWAV" -l en -nt --no-prints -otxt -of "$TMPWAV.out" >/dev/null 2>&1

if [[ -f "$TMPWAV.out.txt" ]]; then
  # Trim leading/trailing whitespace
  sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' "$TMPWAV.out.txt"
else
  echo ""
fi
