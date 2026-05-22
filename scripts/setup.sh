#!/usr/bin/env bash
# One-time setup: install brew deps, download Whisper model, verify macOS voice.
set -euo pipefail

echo "==> Checking macOS"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: macOS only (you're on $(uname -s))." >&2
  exit 1
fi

echo "==> Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "ERROR: Homebrew not found. Install from https://brew.sh" >&2
  exit 1
fi

echo "==> Installing sox and whisper-cpp"
brew install sox whisper-cpp

echo "==> Verifying whisper-cli binary"
if ! command -v whisper-cli >/dev/null 2>&1; then
  echo "ERROR: 'whisper-cli' not found after install." >&2
  echo "Homebrew may have renamed the binary. Try:" >&2
  echo "  brew list whisper-cpp | grep bin" >&2
  echo "and update scripts/record.sh accordingly." >&2
  exit 1
fi
echo "    OK: $(command -v whisper-cli)"

MODEL_DIR="$HOME/.cache/whisper-cpp"
MODEL_FILE="$MODEL_DIR/ggml-small.en.bin"
echo "==> Whisper model"
if [[ -f "$MODEL_FILE" ]]; then
  echo "    Already present: $MODEL_FILE"
else
  mkdir -p "$MODEL_DIR"
  echo "    Downloading ggml-small.en.bin (~466MB) to $MODEL_FILE"
  curl -L --fail -o "$MODEL_FILE" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
fi

echo "==> Checking macOS Vietnamese voice 'Linh'"
if say -v "?" | grep -qi "^Linh "; then
  echo "    OK: Linh is installed."
else
  cat <<'MSG'
    WARNING: Vietnamese voice 'Linh' not found.
    Without it, speak.sh will fall back to a non-Vietnamese voice and
    pronunciation of Vietnamese prompts will be wrong.

    To install:
      System Settings → Accessibility → Spoken Content
        → System Voice → Manage Voices...
        → Vietnamese → Linh → Download

    Or set SPEAK_VOICE to a Vietnamese voice you do have, e.g.:
      export SPEAK_VOICE="Linh (Enhanced)"
MSG
fi

echo
echo "✓ Setup done."
echo "Smoke test:"
echo "  ./scripts/speak.sh 'Xin chào'"
echo "  ./scripts/record.sh"
