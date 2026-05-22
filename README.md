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
| `speak.sh` | `SPEAK_VOICE` | `Linh` | macOS voice name |
| `speak.sh` | `SPEAK_RATE` | `175` | Words per minute |
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

## License

Personal use.
