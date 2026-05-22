# English Speaking Practice — Voice Loop with Claude Code

**Date:** 2026-05-22
**Author:** vuongluu (Vietnamese fullstack dev, Claude MAX subscriber)
**Status:** Draft — pending review

## Goal

Tool luyện nói tiếng Anh giao tiếp cá nhân, chạy local trên macOS, tận dụng Claude MAX subscription (không tốn thêm API cost).

**Core loop:**
1. Claude đưa ra 1 câu tiếng Việt (TTS đọc cho user nghe + in chữ).
2. User nói câu đó bằng tiếng Anh.
3. Whisper transcribe → Claude feedback (grammar, từ vựng, pronunciation note nếu có signal).
4. Move on sang câu mới — không retry, không tracking, không session log.

Cảm hứng: kênh TikTok @ttrangnim (dạy English giao tiếp theo chủ đề), nhưng adapt thành công cụ chủ động luyện nói cho dev bận làm việc.

## Non-goals (V1)

- Web UI / mobile app / Telegram bot — desktop terminal là đủ.
- Spaced repetition, mistake log, progress tracking — stateless mỗi session.
- Topic curriculum / level system — content random, đa dạng.
- Retry mechanic — feedback xong là move on.
- Phoneme-level pronunciation scoring (Speechace / Azure / ELSA) — chỉ rough note từ transcript Whisper.
- Multi-user, cloud sync, mobile.

## Constraints & Context

- **User:** Vietnamese fullstack dev, đang ở level "kém English communication", muốn cải thiện.
- **Platform:** macOS (Apple Silicon ưu tiên).
- **Subscription:** Claude MAX $200/tháng — phải dùng qua Claude Code CLI để free.
- **Use case:** dùng lúc làm việc trên Mac, 10-20 phút giữa giờ.
- **Voice:** mic + loa máy Mac.

## Decisions (đã chốt qua brainstorm)

| # | Decision | Rationale |
|---|---|---|
| D1 | Chạy qua **Claude Code CLI** (skill + bash scripts) | Free dưới MAX; native chat surface; tận dụng được tool calling |
| D2 | **Content random/diverse**, không theo topic cố định | User chọn: đa dạng tình huống, không bị nhàm |
| D3 | **Whisper local** (small.en) cho STT, không API | Free, low latency trên Apple Silicon, đủ accuracy 80% nhu cầu |
| D4 | **macOS `say -v Linh`** cho TTS tiếng Việt | Built-in, free, giọng tự nhiên |
| D5 | **Feedback + move on**, không retry | User muốn pace nhanh, nhiều expose hơn là deepen từng lỗi |
| D6 | **Stateless** — không lưu lịch sử | Simplest V1; nếu cần track sau này, thêm sau |
| D7 | Pronunciation feedback **cơ bản** từ Whisper transcript (so sánh với câu mong đợi) | Trade-off accuracy/cost; phoneme-level chưa cần |
| D8 | Skill ở **project-level** (`.claude/skills/`) | Version cùng repo, dễ chia sẻ máy khác |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Terminal: `claude`                    │
│                                                          │
│   User ──► /english-practice ──► Skill activates         │
│                                                          │
│   ┌────────────────────────────────────────────────┐    │
│   │  Claude (orchestrator)                         │    │
│   │  • Sinh câu tiếng Việt (random topic)          │    │
│   │  • Đọc transcript user → đánh giá              │    │
│   │  • Đưa feedback (grammar / pronunciation hint) │    │
│   └────────────────────────────────────────────────┘    │
│            │                            ▲                │
│            │ Bash tool calls            │ transcript     │
│            ▼                            │                │
│   ┌─────────────────┐         ┌──────────────────────┐  │
│   │  scripts/       │         │  scripts/            │  │
│   │  speak.sh       │         │  record.sh           │  │
│   │  ─────────      │         │  ─────────           │  │
│   │  macOS `say`    │         │  sox `rec` (silence  │  │
│   │  -v Linh        │         │  auto-detect)        │  │
│   │  (Vi voice)     │         │      ↓               │  │
│   │                 │         │  whisper-cli         │  │
│   │                 │         │  (English STT)       │  │
│   └─────────────────┘         └──────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Boundary nguyên tắc:**
- Claude = logic ngôn ngữ (sinh câu, đánh giá).
- Bash scripts = I/O audio (record, play). Predictable, không có "AI magic".
- Không có state file, không có database.

## Component Spec

### `scripts/speak.sh` — TTS tiếng Việt

```bash
#!/usr/bin/env bash
# Usage: ./speak.sh "Hôm nay trời đẹp quá."
set -euo pipefail
TEXT="${1:?Missing text}"
VOICE="${SPEAK_VOICE:-Linh}"

say -v "$VOICE" -r 175 "$TEXT"
```

- **Input:** 1 đối số = câu tiếng Việt.
- **Output:** phát loa.
- **Env tweak:** `SPEAK_VOICE` (default `Linh`).
- **Yêu cầu setup:** macOS voice `Linh` đã tải (System Settings → Accessibility → Spoken Content → Manage Voices).

### `scripts/record.sh` — Mic + Whisper STT

```bash
#!/usr/bin/env bash
# Usage: ./record.sh
# Output (stdout): transcript text. Stderr: progress logs.
set -euo pipefail

TMPWAV="$(mktemp -t engprac).wav"
trap 'rm -f "$TMPWAV" "$TMPWAV.out.txt"' EXIT

MODEL="${WHISPER_MODEL:-$HOME/.cache/whisper-cpp/ggml-small.en.bin}"
MAX_SECONDS="${RECORD_MAX_SECONDS:-15}"
SILENCE_TAIL="${SILENCE_TAIL:-1.5}"
SILENCE_THRESHOLD="${SILENCE_THRESHOLD:-3%}"

echo "🎤 Đang nghe... (nói xong giữ im 1.5s, hoặc Ctrl-C)" >&2

rec -q -r 16000 -c 1 "$TMPWAV" \
    silence 1 0.1 "$SILENCE_THRESHOLD" 1 "$SILENCE_TAIL" "$SILENCE_THRESHOLD" \
    trim 0 "$MAX_SECONDS" 2>/dev/null

whisper-cli -m "$MODEL" -f "$TMPWAV" -l en -nt --no-prints -otxt -of "$TMPWAV.out" >/dev/null 2>&1

cat "$TMPWAV.out.txt"
```

- **Output:** stdout = transcript (có thể rỗng nếu im lặng).
- **Env tweak:** `WHISPER_MODEL`, `SILENCE_TAIL`, `SILENCE_THRESHOLD`, `RECORD_MAX_SECONDS`.
- **Exit code:** 0 nếu OK (kể cả transcript rỗng); != 0 nếu mic/whisper lỗi.

### `scripts/setup.sh` — One-time install

```bash
#!/usr/bin/env bash
set -euo pipefail

brew install sox whisper-cpp

MODEL_DIR="$HOME/.cache/whisper-cpp"
MODEL_FILE="$MODEL_DIR/ggml-small.en.bin"
if [[ ! -f "$MODEL_FILE" ]]; then
  mkdir -p "$MODEL_DIR"
  curl -L -o "$MODEL_FILE" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
fi

echo "✓ Setup done."
echo "Lần đầu chạy record.sh sẽ có macOS popup xin quyền mic."
echo "Voice Linh: System Settings → Accessibility → Spoken Content → Manage Voices → Vietnamese → Linh"
echo "Test: ./scripts/speak.sh 'Xin chào' && ./scripts/record.sh"
```

### `.claude/skills/english-practice.md` — Skill orchestrator

```markdown
---
name: english-practice
description: Luyện nói tiếng Anh giao tiếp qua voice. Use when user types `/english-practice`, "luyện English", "bắt đầu luyện nói", hoặc tương tự. Claude sẽ luân phiên đưa câu tiếng Việt qua TTS, ghi âm câu English của user, transcribe bằng Whisper, rồi feedback.
---

# English Speaking Practice Loop

Bạn là coach English giao tiếp cho user. Vận hành theo loop sau cho đến khi user nói "stop", "dừng", "thôi", hoặc Ctrl-C.

## Vòng lặp một câu

1. **Sinh 1 câu tiếng Việt** — conversational, độ dài 8-18 từ, lấy ngẫu nhiên từ nhiều chủ đề (xem Chủ đề bên dưới). KHÔNG lặp chủ đề liền 2 câu.
2. **Gọi `bash scripts/speak.sh "<câu Việt>"`** — đọc câu cho user nghe.
3. **In câu Việt ra terminal** kèm prefix `🇻🇳`, để user vừa nghe vừa đọc được.
4. **Gọi `bash scripts/record.sh`** — capture user nói English. Output stdout là transcript.
5. **Đánh giá transcript** (xem Feedback format).
6. **Sang câu mới** — không retry, không hỏi user có muốn lặp.

## Chủ đề (luân phiên ngẫu nhiên)

Daily life · Ăn uống / café · Đi lại · Công việc dev (standup, code review, design discussion) · Du lịch · Mua sắm · Sức khoẻ · Giao tiếp công sở · Tâm trạng · Smalltalk · Interview · Gia đình / bạn bè.

Mỗi câu chọn 1 chủ đề khác chủ đề câu trước.

## Câu tiếng Việt cần

- Tự nhiên, hội thoại; không dịch máy.
- Đủ thử thách (có 1 cấu trúc/idiom không trivial).
- Tránh quá học thuật.
- Ví dụ tốt: "Sếp tôi vừa bảo dời cuộc họp sang chiều mai vì khách hàng bận."
- Ví dụ tránh: "Hôm nay tôi đi học."

## Feedback format

```
🎙️  You said: <transcript>
✅ Model:    <câu English tự nhiên>

📝 Feedback:
• <điểm 1>
• <điểm 2 — nếu có>

🔊 Pronunciation: <chỉ note nếu có signal từ Whisper>
```

**Quy tắc:**
- Transcript đúng/gần đúng → khen ngắn, qua câu mới.
- Sai grammar nhẹ (article, preposition) → 1 bullet ngắn + why.
- Sai cấu trúc lớn → 1-2 bullet, gợi ý cách nghĩ lại.
- Transcript khác xa câu mong đợi → ưu tiên Model answer, ít chê.
- Pronunciation note CHỈ khi: Whisper transcribe ra từ rất khác từ mong đợi, hoặc bỏ qua một từ. Note ngắn với IPA: `"thought" /θɔːt/ — đặt lưỡi giữa răng cho âm /θ/`.

## Edge cases

- Transcript rỗng → in `❓ Không nghe rõ, sang câu khác nhé.` rồi đi tiếp.
- User type chữ thay vì nói:
  - "stop"/"dừng"/"thôi" → kết thúc.
  - Câu hỏi khác → trả lời ngắn rồi tiếp loop.
- Script báo lỗi (exit != 0) → in lỗi gốc, hỏi user check setup; không loop tiếp.

## Bắt đầu session

In welcome 1 dòng:
```
🎯 English Practice — feedback + move on, stateless.
   Gõ "stop" để dừng. Bắt đầu nhé!
```
Rồi vào câu đầu ngay.
```

## Project Layout

```
enghlish_q_n_a/
├── .claude/skills/english-practice.md
├── scripts/
│   ├── setup.sh
│   ├── speak.sh
│   └── record.sh
├── docs/superpowers/specs/2026-05-22-english-practice-design.md
├── .gitignore           # *.wav, .DS_Store
└── README.md
```

## Setup (cho user lần đầu)

```bash
cd /Users/vuongluu/Documents/learning/enghlish_q_n_a
chmod +x scripts/*.sh
./scripts/setup.sh

# (Tuỳ chọn) Tải giọng Vi "Linh" qua System Settings nếu chưa có.

./scripts/speak.sh "Xin chào, bạn khoẻ không?"   # smoke test TTS
./scripts/record.sh                              # smoke test STT

claude
# rồi gõ: /english-practice
```

## Dependencies

| Dep | Cài qua | Vì sao |
|---|---|---|
| Claude Code CLI | đã có (user là MAX subscriber) | Orchestrator + chat surface |
| `sox` | `brew install sox` | Mic recording + silence detection |
| `whisper-cpp` | `brew install whisper-cpp` (CLI tên `whisper-cli`) | STT local |
| Whisper model `small.en` (~466MB) | `setup.sh` curl từ HuggingFace | Model trọng số |
| macOS voice "Linh" | System Settings (1-time) | TTS tiếng Việt |

**Không cần:** Node, Python, Docker, database, API keys, network 24/7 (chỉ cần net khi Claude gọi LLM).

## Verification Plan

### Smoke test từng script

| Test | Command | Pass criteria |
|---|---|---|
| TTS Vi | `./scripts/speak.sh "Xin chào"` | Nghe loa, giọng Linh |
| Mic + Whisper | `./scripts/record.sh` rồi nói "I want coffee" | Stdout in transcript đúng trong ~5s |
| Silence cut | `record.sh`, im lặng | Tự thoát sau ~1.5s, transcript rỗng, exit 0 |
| Model missing | Xoá model, chạy record | Báo lỗi rõ + path |
| Mic permission | Lần đầu | macOS popup; nếu deny → script báo lỗi |

### End-to-end acceptance

Chạy `claude` → `/english-practice`. Pass checklist:

- [ ] Welcome 1 dòng, vào câu đầu ngay.
- [ ] Câu Việt vừa nghe loa, vừa thấy chữ (🇻🇳 prefix).
- [ ] Câu tự nhiên, có challenge, không quá đơn giản.
- [ ] Transcript hiện ra trong ~3-5s sau khi user nói xong.
- [ ] Feedback đúng format (You said / Model / Feedback bullets).
- [ ] Pronunciation section CHỈ xuất hiện khi có signal.
- [ ] Sang câu mới ngay, không hỏi retry, không hỏi topic.
- [ ] Chủ đề câu 2 ≠ câu 1.
- [ ] Gõ `stop` → kết thúc clean.
- [ ] Ctrl-C → thoát clean, tmp .wav được xoá.

### Edge case test

| Case | Reproduce | Expected |
|---|---|---|
| Im lặng cả câu | record.sh → không nói | "❓ Không nghe rõ, sang câu khác" |
| Nói nhầm tiếng Việt | Trả lời bằng Vi | Transcript kỳ quặc; Claude feedback nhẹ + Model rõ |
| Hỏi giữa loop | Type "giải thích thì hiện tại hoàn thành" | Claude trả lời ngắn, tiếp loop |
| "Câu dễ hơn" | Type | Câu kế đơn giản hơn, vẫn random topic |
| Network down | Tắt wifi | Whisper local vẫn chạy; chỉ Claude cần net |
| Tmp leak | Ctrl-C giữa record | Trap xoá .wav |

### Performance acceptance

- Round-trip nói xong → feedback hiện: **≤ 5s** trên M-series Mac.
- Whisper transcribe 10s audio: **≤ 3s**.
- TTS bắt đầu phát: gần instant.

Nếu chậm hơn → fallback: hạ model xuống `base.en` (~140MB).

## Known Limitations (chấp nhận)

- Không phoneme-level scoring.
- Không tracking / progress.
- Không retry trên câu sai.
- Silence detection có thể cắt sớm/muộn → user nói lại.
- Whisper English-only: nói nhầm Vi → transcript kỳ quặc (đây là feature, lộ lỗi rõ).

## Future Migration Path (V2 ideas, không làm V1)

- Move 2 bash scripts thành **local MCP server** với tool schemas rõ ràng → ít hallucinate, async streaming.
- Add **mistake log** (JSON file) + `/english-review` command để ôn lại.
- Add **topic mode**: `/english-practice food` → giới hạn chủ đề.
- Add **phoneme scoring** qua Azure Pronunciation Assessment API (~$1/h).
- Web UI thin layer chạy localhost (Next.js) gọi cùng scripts.

## Dev Effort Estimate

- Skill file + 3 scripts + README: ~4-6 giờ.
- Smoke test + tinh chỉnh silence threshold: 1-2 giờ.
- Total V1: **1 buổi làm việc**.
