# English Practice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local English-speaking-practice tool that runs via Claude Code CLI on macOS: Claude generates a Vietnamese sentence (TTS-spoken via macOS `say`), user speaks the English version, Whisper transcribes, Claude gives concise feedback, loop continues until user stops.

**Architecture:** A Claude Code project-level skill orchestrates the loop; three bash scripts handle I/O (TTS, mic+STT, one-time setup). Stateless — no session log, no retry. Free under Claude MAX.

**Tech Stack:** Claude Code CLI · macOS `say` (Vietnamese voice "Linh") · `sox` (recording + silence detection) · `whisper-cpp` (`whisper-cli` binary) + Whisper `small.en` model · plain bash.

**Spec:** [docs/superpowers/specs/2026-05-22-english-practice-design.md](../specs/2026-05-22-english-practice-design.md)

---

## File Structure

| File | Purpose | Owner-task |
|---|---|---|
| `.gitignore` | Ignore `.wav` tmp, `.DS_Store` | Task 1 |
| `README.md` | Quick start, env vars, troubleshooting | Task 1 (skeleton) + Task 7 (polish) |
| `scripts/setup.sh` | One-time install: brew deps, model download, voice check | Task 2 |
| `scripts/speak.sh` | TTS Vietnamese (macOS `say -v Linh`) | Task 3 |
| `scripts/record.sh` | sox `rec` → whisper-cli → transcript | Task 4 |
| `.claude/skills/english-practice.md` | Skill instructions for Claude | Task 5 |

**Why this split:** Each script has one responsibility. The skill is the only "smart" piece. Scripts are independently testable. No state file — stateless V1.

**Note on testing approach:** Bash scripts don't have a strong TDD framework. We use "manual smoke test" as the verification step for each script (run it, observe expected output). This matches the spec's verification plan.

---

## Pre-flight: Working directory & git init

Project lives at `/Users/vuongluu/Documents/learning/enghlish_q_n_a`. Currently not a git repo (per session context). Task 1 initializes git.

---

## Task 1: Bootstrap repo (`.gitignore`, README skeleton, git init)

**Files:**
- Create: `.gitignore`
- Create: `README.md` (skeleton, expanded in Task 7)

- [ ] **Step 1: Initialize git repo and verify cwd**

```bash
cd /Users/vuongluu/Documents/learning/enghlish_q_n_a
git init
git status
```

Expected: `Initialized empty Git repository in .../enghlish_q_n_a/.git/` and `git status` shows untracked files (the spec/plan docs you've already saved).

- [ ] **Step 2: Create `.gitignore`**

```
# Audio tmp files from record.sh
*.wav

# macOS metadata
.DS_Store

# Whisper output side-files (just in case)
*.wav.out.txt
```

- [ ] **Step 3: Create `README.md` skeleton**

```markdown
# English Practice — Voice Loop with Claude

Luyện nói tiếng Anh giao tiếp qua voice với Claude Code. $0 dưới Claude MAX.

## Quick start

\`\`\`bash
chmod +x scripts/*.sh
./scripts/setup.sh
claude
# rồi gõ: /english-practice
\`\`\`

> Hướng dẫn chi tiết sẽ bổ sung sau khi build xong.
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore README.md docs/
git commit -m "chore: bootstrap repo with gitignore, README skeleton, and spec/plan docs"
```

Expected: 1 commit, includes spec + plan + skeleton files.

---

## Task 2: `scripts/setup.sh` — one-time install + verification

**Files:**
- Create: `scripts/setup.sh`

**Notes:**
- Address advisory #1: detect actual whisper-cpp binary name (it ships as `whisper-cli` on current Homebrew; verify after install).
- Address advisory #2: explicitly check macOS voice "Linh" availability and print clear remediation if missing.

- [ ] **Step 1: Write `scripts/setup.sh`**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/setup.sh
```

- [ ] **Step 3: Run setup.sh and verify**

```bash
./scripts/setup.sh
```

Expected output highlights:
- `OK: /opt/homebrew/bin/whisper-cli` (or `/usr/local/bin/whisper-cli` on Intel)
- Either `Already present: ...ggml-small.en.bin` or download progress + completion
- `OK: Linh is installed.` OR the warning block with install instructions

If whisper-cli isn't found: stop and investigate (`brew list whisper-cpp | grep bin`) — update binary name throughout plan if it actually differs.

- [ ] **Step 4: Commit**

```bash
git add scripts/setup.sh
git commit -m "feat: add setup.sh — install deps, fetch Whisper model, verify Vietnamese voice"
```

---

## Task 3: `scripts/speak.sh` — TTS Vietnamese

**Files:**
- Create: `scripts/speak.sh`

- [ ] **Step 1: Write `scripts/speak.sh`**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/speak.sh
```

- [ ] **Step 3: Smoke test — listen with default voice**

```bash
./scripts/speak.sh "Xin chào, hôm nay trời đẹp quá."
```

Expected: speaker plays Vietnamese audio in Linh's voice (or fallback voice with warning from setup if Linh missing). Returns to shell with exit code 0.

- [ ] **Step 4: Smoke test — override voice**

```bash
SPEAK_VOICE=Samantha ./scripts/speak.sh "Hello world"
```

Expected: plays in Samantha (English voice). Confirms env override works.

- [ ] **Step 5: Smoke test — missing arg fails loudly**

```bash
./scripts/speak.sh
```

Expected: exits non-zero with `Usage: speak.sh "text"`. (This is from the `${1:?...}` parameter expansion.)

- [ ] **Step 6: Commit**

```bash
git add scripts/speak.sh
git commit -m "feat: add speak.sh — TTS Vietnamese via macOS say with voice override"
```

---

## Task 4: `scripts/record.sh` — record + transcribe

**Files:**
- Create: `scripts/record.sh`

- [ ] **Step 1: Write `scripts/record.sh`**

```bash
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

TMPWAV="$(mktemp -t engprac).wav"
trap 'rm -f "$TMPWAV" "$TMPWAV.out.txt"' EXIT

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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/record.sh
```

- [ ] **Step 3: Smoke test — speak a short English sentence**

```bash
./scripts/record.sh
# Wait for "🎤 Đang nghe..." prompt, then say clearly:
#   "I want to drink some coffee"
# Then stay silent ~2 seconds for auto-stop.
```

Expected (stdout): `I want to drink some coffee` (or very close). Round-trip should be ≤5s on Apple Silicon. Exit code 0.

- [ ] **Step 4: Smoke test — silence cut**

```bash
./scripts/record.sh
# Don't say anything. Stay silent.
```

Expected: returns within ~1.5–2s. Stdout is empty (or just a newline). Exit code 0.

- [ ] **Step 5: Smoke test — model missing error path**

```bash
WHISPER_MODEL=/tmp/nonexistent.bin ./scripts/record.sh
```

Expected: exits non-zero. Stderr says model not found at the bad path + suggests `setup.sh`.

- [ ] **Step 6: Smoke test — tmp file cleanup**

```bash
ls /tmp/engprac* 2>/dev/null || echo "no leftover tmp files"
```

Expected: `no leftover tmp files` (trap cleaned up).

- [ ] **Step 7: Commit**

```bash
git add scripts/record.sh
git commit -m "feat: add record.sh — sox + whisper-cli with silence detection and error handling"
```

---

## Task 5: Skill file — orchestrator

**Files:**
- Create: `.claude/skills/english-practice.md`

**Notes:**
- Address advisory #3: include concrete examples of when to emit a pronunciation note (vs not).
- Address advisory #4: trigger description covers both `/english-practice` and natural phrases.

- [ ] **Step 1: Create directory**

```bash
mkdir -p .claude/skills
```

- [ ] **Step 2: Write `.claude/skills/english-practice.md`**

````markdown
---
name: english-practice
description: Luyện nói tiếng Anh giao tiếp qua voice. Use when user types `/english-practice`, "luyện English", "bắt đầu luyện nói", "english practice", "luyện nói tiếng Anh", hoặc tương tự. Claude sẽ luân phiên đưa câu tiếng Việt qua TTS, ghi âm câu English của user, transcribe bằng Whisper, rồi feedback.
---

# English Speaking Practice Loop

Bạn là coach English giao tiếp cho user (Vietnamese fullstack dev). Vận hành loop sau cho đến khi user nói "stop", "dừng", "thôi", hoặc Ctrl-C.

## Vòng lặp một câu

1. **Sinh 1 câu tiếng Việt** — conversational, độ dài 8-18 từ, lấy ngẫu nhiên từ nhiều chủ đề (xem mục Chủ đề). KHÔNG lặp chủ đề liền 2 câu.
2. **In câu Việt ra terminal** kèm prefix `🇻🇳`.
3. **Gọi `bash scripts/speak.sh "<câu Việt>"`** qua Bash tool — đọc câu cho user nghe.
4. **Gọi `bash scripts/record.sh`** qua Bash tool — capture user nói English. Output stdout là transcript.
5. **Đánh giá transcript** (xem Feedback format).
6. **Sang câu mới** — KHÔNG retry, KHÔNG hỏi user có muốn lặp.

## Chủ đề (luân phiên ngẫu nhiên)

Daily life · Ăn uống / café · Đi lại · Công việc dev (standup, code review, design discussion) · Du lịch · Mua sắm · Sức khoẻ · Giao tiếp công sở · Tâm trạng · Smalltalk · Interview · Gia đình / bạn bè.

Mỗi câu chọn 1 chủ đề khác chủ đề câu trước.

## Câu tiếng Việt cần

- Tự nhiên, hội thoại; không dịch máy.
- Đủ thử thách (có 1 cấu trúc/idiom không trivial: phrasal verb, conditional, present perfect, relative clause…).
- Tránh quá học thuật.
- ✅ Tốt: "Sếp tôi vừa bảo dời cuộc họp sang chiều mai vì khách hàng bận."
- ❌ Tránh: "Hôm nay tôi đi học." (quá đơn giản, không đáng challenge)

## Feedback format

```
🎙️  You said: <transcript>
✅ Model:    <câu English tự nhiên nhất cho câu Việt vừa rồi>

📝 Feedback:
• <điểm 1>
• <điểm 2 — nếu có>

🔊 Pronunciation: <chỉ note nếu có signal — xem ví dụ dưới>
```

**Quy tắc feedback:**
- Transcript đúng/gần đúng câu Model → khen ngắn ("Nice, natural!") rồi qua câu mới.
- Sai grammar nhẹ (article, preposition) → 1 bullet ngắn + giải thích why.
- Sai cấu trúc lớn (sai thì, sai chủ ngữ) → 1-2 bullet, gợi ý cách nghĩ lại.
- Transcript khác xa câu mong đợi → ưu tiên đưa Model rõ, ít chê.

**Pronunciation note — CHỈ thêm khi có signal cụ thể:**

| Signal trong transcript | Inference | Note |
|---|---|---|
| Whisper thiếu hẳn 1 từ quan trọng | User phát âm yếu chữ đó | "X" /IPA/ — cách đặt miệng |
| Whisper ra từ rất khác từ mong đợi (vd: "tree" → "three", "thought" → "taught") | User nhầm âm vị (/θ/ vs /t/, /θ/ vs /tɔː/) | Chỉ ra âm vị + cách tạo âm |
| Transcript thiếu ending consonant (vd "want" → "wan") | Endings yếu | "Nhớ nhả âm cuối /t/" |

**KHÔNG thêm pronunciation note khi:**
- Whisper transcribe sạch (= phát âm ổn).
- Lỗi chỉ là từ vựng/grammar, không phải âm.
- Không có signal cụ thể (đừng bịa).

## Edge cases

- **Transcript rỗng** → in `❓ Không nghe rõ, sang câu khác nhé.` rồi đi tiếp.
- **User type chữ thay vì nói:**
  - "stop" / "dừng" / "thôi" / "quit" → kết thúc với 1 dòng goodbye ngắn.
  - "câu dễ hơn" / "easier" → câu kế đơn giản hơn (8-12 từ), vẫn random topic.
  - "giải thích thêm" / câu hỏi grammar khác → trả lời ngắn trong 2-3 câu, RỒI tiếp loop (sinh câu Việt mới).
- **Script báo lỗi** (exit code != 0 từ Bash tool) → in stderr gốc cho user, gợi ý chạy `./scripts/setup.sh`, KHÔNG loop tiếp.

## Bắt đầu session

Khi skill kích hoạt, in welcome:
```
🎯 English Practice — feedback + move on, stateless.
   Gõ "stop" để dừng. Bắt đầu nhé!
```
Rồi vào câu đầu tiên ngay (KHÔNG hỏi topic, KHÔNG hỏi level).
````

- [ ] **Step 3: Smoke test — skill file is valid markdown with frontmatter**

```bash
head -20 .claude/skills/english-practice.md
```

Expected: shows the `---` frontmatter with `name:` and `description:` fields, followed by `# English Speaking Practice Loop`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/english-practice.md
git commit -m "feat: add english-practice skill with loop instructions and feedback rules"
```

---

## Task 6: End-to-end acceptance test

**No files to create.** This is a manual integration test against the spec's acceptance checklist.

- [ ] **Step 1: Open new terminal session and launch claude**

```bash
cd /Users/vuongluu/Documents/learning/enghlish_q_n_a
claude
```

- [ ] **Step 2: Trigger the skill via slash command**

In the claude session, type:
```
/english-practice
```

Expected: skill activates, welcome banner appears, Claude immediately generates first Vietnamese sentence (no setup questions).

- [ ] **Step 3: Verify first round-trip**

Run the acceptance checklist from the spec:
- [ ] Welcome banner is 1 line, no ceremony
- [ ] First Vietnamese sentence is spoken via speakers (you HEAR it)
- [ ] First Vietnamese sentence is also printed to terminal with 🇻🇳 prefix
- [ ] Sentence feels natural, not machine-translated, has challenge (not "Hôm nay tôi đi học")
- [ ] `🎤 Đang nghe...` prompt appears
- [ ] You speak English; transcript appears in ~3-5s
- [ ] Feedback follows format: `🎙️ You said` / `✅ Model` / `📝 Feedback` bullets
- [ ] Pronunciation section appears ONLY when there's a real signal (try both: speak cleanly → no pronunciation note; deliberately mumble "th" sound → expect a note)
- [ ] Claude moves to next sentence immediately, no "retry?" prompt
- [ ] Sentence 2 topic ≠ sentence 1 topic

- [ ] **Step 4: Verify trigger phrase variant**

Exit (`stop`), restart claude, this time type:
```
luyện English
```

Expected: skill activates (same as slash command). If it doesn't activate, the skill description may need expansion — go fix and re-test.

- [ ] **Step 5: Verify edge cases**

In a running session, test each:
- [ ] **Empty transcript**: stay silent during `record.sh`. Expected: `❓ Không nghe rõ, sang câu khác nhé.` then next sentence.
- [ ] **Type instead of speak**: type "câu dễ hơn". Expected: next sentence is simpler.
- [ ] **Inline question**: type "giải thích thì hiện tại hoàn thành cho tôi". Expected: brief explanation (2-3 sentences), then loop continues with new sentence.
- [ ] **Stop**: type `stop`. Expected: clean exit, no leftover `/tmp/engprac*.wav`.

```bash
# After stopping:
ls /tmp/engprac* 2>/dev/null || echo "clean"
```

Expected: `clean`.

- [ ] **Step 6: Performance check**

During the session, eyeball:
- [ ] Round-trip (silence-cut → feedback visible): ≤ 5s on M-series Mac
- [ ] Whisper transcribe phase: ≤ 3s for ~10s audio

If slower → set `WHISPER_MODEL` env to `base.en` model (download separately) and re-test.

- [ ] **Step 7: Document any deviations**

If something didn't match: open an issue note in a fresh `docs/superpowers/notes/2026-05-22-acceptance-findings.md` or append to README's troubleshooting section. Then return to the relevant task to fix.

- [ ] **Step 8: Commit (if any minor fixes were made during acceptance)**

```bash
git status
# If anything changed during acceptance fixes:
git add -A
git commit -m "fix: minor adjustments from end-to-end acceptance test"
```

---

## Task 7: README polish

**Files:**
- Modify: `README.md` (replace skeleton with full doc)

- [ ] **Step 1: Replace `README.md` content**

```markdown
# English Practice — Voice Loop with Claude

Luyện nói tiếng Anh giao tiếp với Claude Code, $0 dưới Claude MAX subscription.

**Flow:** Claude đọc câu tiếng Việt → bạn nói câu English → Whisper transcribe → Claude feedback → câu mới. Stateless, không retry, random topics.

## Yêu cầu

- macOS (dùng `say` cho TTS Vi)
- [Claude Code CLI](https://claude.com/code) đã login (subscription MAX hoặc Pro)
- [Homebrew](https://brew.sh)

## Quick start

\`\`\`bash
chmod +x scripts/*.sh
./scripts/setup.sh        # cài sox, whisper-cpp, model; check voice Linh

# Smoke test 2 script:
./scripts/speak.sh "Xin chào, hôm nay trời đẹp."
./scripts/record.sh       # nói tiếng Anh trong ~5s

# Khởi động:
claude
# rồi gõ: /english-practice
\`\`\`

## Cài voice tiếng Việt (1 lần)

Nếu `setup.sh` báo voice **Linh** chưa có:

1. System Settings → Accessibility → Spoken Content
2. System Voice → **Manage Voices...**
3. Tìm Vietnamese → **Linh** → Download

Hoặc dùng voice Vi khác:
\`\`\`bash
export SPEAK_VOICE="Linh (Enhanced)"   # hoặc voice Vi nào bạn đã có
\`\`\`

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
\`\`\`bash
export WHISPER_MODEL=~/.cache/whisper-cpp/ggml-base.en.bin
\`\`\`
(Download riêng từ https://huggingface.co/ggerganov/whisper.cpp)

## Layout

\`\`\`
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
\`\`\`

## License

Personal use.
```

- [ ] **Step 2: Smoke test — markdown renders**

```bash
head -30 README.md
```

Expected: valid markdown, no broken backticks/escapes.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: expand README with setup, tinh chỉnh, troubleshooting"
```

---

## Done criteria

All 7 tasks complete. Final verification:

```bash
git log --oneline
```

Expected: ~7 commits, in this order:
1. `chore: bootstrap repo with gitignore, README skeleton, and spec/plan docs`
2. `feat: add setup.sh — install deps, fetch Whisper model, verify Vietnamese voice`
3. `feat: add speak.sh — TTS Vietnamese via macOS say with voice override`
4. `feat: add record.sh — sox + whisper-cli with silence detection and error handling`
5. `feat: add english-practice skill with loop instructions and feedback rules`
6. `fix: minor adjustments from end-to-end acceptance test` (optional, only if needed)
7. `docs: expand README with setup, tinh chỉnh, troubleshooting`

```bash
tree -a -I '.git|node_modules|*.wav' . 2>/dev/null || find . -type f -not -path './.git/*' | sort
```

Expected files:
- `.claude/skills/english-practice.md`
- `.gitignore`
- `README.md`
- `docs/superpowers/plans/2026-05-22-english-practice.md`
- `docs/superpowers/specs/2026-05-22-english-practice-design.md`
- `scripts/record.sh`
- `scripts/setup.sh`
- `scripts/speak.sh`

Final smoke run:
```bash
claude
/english-practice
# Run 2-3 sentences, verify acceptance checklist from Task 6 step 3.
stop
```

---

## Notes for the engineer

- **Bash is not Python.** Don't add TDD frameworks. Each script has a smoke test step that exercises happy path + error paths. That's the test surface.
- **macOS-only.** Don't generalize to Linux. If you find yourself adding `case "$(uname)" in Linux)`, stop and ask.
- **Stateless.** No JSON file for history. No SQLite. No config file. Env vars are the only configuration mechanism.
- **Skill drift risk.** If you change a script's interface (e.g., rename an env var), update both the skill description AND the README. The skill calls scripts via Bash tool, so behavior changes propagate.
- **Don't add features.** No "topic mode", no "review mistakes", no MCP migration. Those are in the spec's "Future Migration Path" — out of scope for V1.
