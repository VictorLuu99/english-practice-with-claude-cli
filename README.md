# English Practice — Voice Loop with Claude

Luyện nói tiếng Anh giao tiếp với Claude Code, $0 dưới Claude MAX subscription.

**Flow:** Claude đọc câu tiếng Việt → bạn nói câu English → Whisper transcribe → Claude feedback → câu mới. Stateless, không retry, random topics.

## Yêu cầu

- macOS (dùng `say` cho TTS Vi)
- [Claude Code CLI](https://claude.com/code) đã login (subscription MAX hoặc Pro)
- [Homebrew](https://brew.sh)

## Quick start

```bash
chmod +x scripts/*.sh
./scripts/setup.sh        # cài sox, whisper-cpp, model; check voice Linh

# Smoke test 2 script:
./scripts/speak.sh "Xin chào, hôm nay trời đẹp."
./scripts/record.sh       # nói tiếng Anh trong ~5s

# Khởi động:
claude
# rồi gõ: /english-practice
```

## Cài voice tiếng Việt (1 lần)

Nếu `setup.sh` báo voice **Linh** chưa có:

1. System Settings → Accessibility → Spoken Content
2. System Voice → **Manage Voices...**
3. Tìm Vietnamese → **Linh** → Download

Hoặc dùng voice Vi khác:
```bash
export SPEAK_VOICE="Linh (Enhanced)"   # hoặc voice Vi nào bạn đã có
```

## Tinh chỉnh (env vars)

| Script | Env var | Default | Mô tả |
|---|---|---|---|
| `speak.sh` | `SPEAK_VOICE` | `Linh (Enhanced)` | macOS voice. Tự fallback về `Linh` (compact) nếu Enhanced chưa cài, có warning trên stderr. (Apple không có Premium cho tiếng Việt — chỉ Linh và Linh Enhanced.) |
| `speak.sh` | `SPEAK_RATE` | `265` | Words per minute (~1.5× tốc độ tự nhiên của Linh). Giảm xuống `175` nếu thấy nhanh quá. |
| `record.sh` | `WHISPER_MODEL` | `~/.cache/whisper-cpp/ggml-small.en.bin` | Path tới model |
| `record.sh` | `SILENCE_TAIL` | `1.5` | Giây im lặng để cắt |
| `record.sh` | `SILENCE_THRESHOLD` | `3%` | Ngưỡng noise (giảm xuống `1%` nếu ngồi yên tĩnh) |
| `record.sh` | `RECORD_MAX_SECONDS` | `15` | Cap độ dài record |

## Dừng session

Gõ `stop` / `dừng` / `thôi` / `quit`, hoặc Ctrl-C.

## Troubleshooting

**"Mic permission denied"** — Lần đầu macOS sẽ popup hỏi quyền. Nếu lỡ deny: System Settings → Privacy & Security → Microphone → bật cho Terminal/iTerm.

**"whisper-cli: command not found"** — Chạy lại `./scripts/setup.sh`. Nếu Homebrew đổi tên binary, check `brew list whisper-cpp | grep bin` và cập nhật `record.sh`.

**Transcript rỗng / silence cắt sớm** — Tăng `SILENCE_TAIL` (vd `2.0`), hoặc giảm `SILENCE_THRESHOLD` xuống `1%` nếu môi trường ồn.

**Whisper chậm** — Đổi sang model nhẹ hơn:
```bash
export WHISPER_MODEL=~/.cache/whisper-cpp/ggml-base.en.bin
```
(Download riêng từ https://huggingface.co/ggerganov/whisper.cpp)

## Layout

```
.
├── .claude/skills/english-practice.md    # Skill orchestrator
├── scripts/
│   ├── setup.sh
│   ├── speak.sh
│   └── record.sh
├── docs/
│   ├── superpowers/specs/    # Design specs
│   └── superpowers/plans/    # Implementation plans
└── README.md
```

## Telegram bot version (iPhone-friendly)

Same loop, but you talk to a Telegram bot from your phone instead of the
terminal. Bot service runs on this macOS host; iPhone is the client.

### Setup (one-time)

1. Create a bot via [@BotFather](https://t.me/BotFather) → copy the
   `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot from your iPhone Telegram app. Then run:
   ```
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[].message.chat.id'
   ```
   to read your `chat_id`.
3. Copy `.env.example` → `.env`, fill in token + chat_ids:
   ```
   TELEGRAM_BOT_TOKEN=123456:abc...
   ALLOWED_CHAT_IDS=<your_chat_id>
   ```
4. Install Python deps:
   ```
   python3.11 -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   ```
5. (Optional) ElevenLabs for a single unified voice (Adam) across Vi + English:
   - Sign up at [elevenlabs.io](https://elevenlabs.io) (free tier ≈ 10k chars/month ≈ 20–30 rounds)
   - Profile → API Keys → create → paste into `.env`:
     ```
     ELEVENLABS_API_KEY=sk_...
     ```
   - Leave empty to stick with macOS `say` (bilingual Linh + Samantha)
   - On any ElevenLabs failure (quota, auth, network) the bot **auto-falls
     back** to `say` for that round — you don't lose the session

### Run

```bash
./scripts/run_bot.sh   # Ctrl-C to stop
```

On iPhone: open Telegram → your bot → `/start` → long-press 🎙 to reply →
`/stop` when done.

Bot only runs while this macOS terminal is open and the laptop is awake.
Whitelist enforced: chats outside `ALLOWED_CHAT_IDS` are silently ignored.

See [tests/smoke.md](tests/smoke.md) for the full manual checklist.

## License

Personal use.
