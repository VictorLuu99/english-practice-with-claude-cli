# Manual Smoke Test — Telegram Bot

Run these by hand on the macOS dev box with the iPhone Telegram app. Not automated.

## Prep

1. `cp .env.example .env`, fill `TELEGRAM_BOT_TOKEN` and `ALLOWED_CHAT_IDS`.
2. `./scripts/run_bot.sh` in a terminal — bot should log "polling Telegram...".

## Checklist

- [ ] **Start round**: Open Telegram → bot → send `/start`. Within ~5s receive:
  - text message starting with `🇻🇳 ...`
  - voice message (Vi) playable in Telegram
- [ ] **Speak reply**: Long-press 🎙 in Telegram → record one English sentence → release. Within ~10s receive:
  - text feedback (transcript / Model / Feedback / Pronunciation if any)
  - voice message (Samantha rate 140 — model English)
  - voice message (Linh — Vi summary ending "Câu tiếp theo.")
  - and **the next round starts automatically** (new 🇻🇳 + voice)
- [ ] **Stop**: Send `/stop`. Bot replies "🛑 Stopped." Sending more voice does NOT loop.
- [ ] **Restart**: Send `/start` after stop → fresh round emitted.
- [ ] **Whitelist deny**: From a second Telegram account NOT in `ALLOWED_CHAT_IDS`, send `/start` → bot stays silent. Logs show "ignored non-allowed chat_id=...".
- [ ] **Network drop**: While bot is in `WAITING_VOICE`, turn off macOS Wi-Fi for 30s → send voice → bot replies "Claude busy, thử lại sau vài giây.", state stays. Turn Wi-Fi back on → resend the same voice → round resumes (no /start needed).
- [ ] **Empty voice**: Send a 0.5s silent recording → bot replies "Không nghe rõ, thử lại.", state stays WAITING_VOICE.
- [ ] **Long voice**: Try to send a 90s voice → bot replies "Voice quá dài (max 60s), thử lại."
- [ ] **Text during WAITING_VOICE**: Send "hi" as text → bot reminds to long-press mic or /stop.
- [ ] **Ctrl-C shutdown**: In the terminal, Ctrl-C → bot logs "shutdown clean" and exits 0.
