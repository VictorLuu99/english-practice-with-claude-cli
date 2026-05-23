#!/usr/bin/env bash
# Launch the Telegram bot. Manual start — Ctrl-C to stop.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  echo "❌ .venv not found. Run: python3.11 -m venv .venv && .venv/bin/pip install -e ."
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "❌ .env not found. Copy .env.example to .env and fill in tokens."
  exit 1
fi

exec .venv/bin/python -m english_bot
