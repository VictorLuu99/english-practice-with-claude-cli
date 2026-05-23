# Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal Telegram bot on macOS that mirrors the existing terminal English-practice loop (Vi prompt → spoken English → corrective feedback), accessible from iPhone Telegram. Stateless per round, whitelist-only, free under Claude MAX.

**Architecture:** Single Python 3.11 process. `python-telegram-bot` long-polls Telegram; per-chat state machine drives one round at a time; Claude Agent SDK (subscription auth) generates Vi prompts and evaluates English transcripts; macOS `say` + `ffmpeg` + `whisper-cli` produce/consume audio via subprocess. Existing shell scripts (`speak.sh`, `record.sh`) stay untouched.

**Tech Stack:** Python 3.11, `python-telegram-bot[ext]` ^21.0, `claude-agent-sdk`, `python-dotenv` ^1.0, `pytest` + `pytest-asyncio`, macOS `say`, Homebrew `ffmpeg` + `whisper-cpp`.

**Spec:** [docs/superpowers/specs/2026-05-23-telegram-bot-design.md](../specs/2026-05-23-telegram-bot-design.md)

---

## File Structure

```
english_bot/
├── __init__.py
├── __main__.py            # entry point + signal handling
├── config.py              # env loading, fail-fast validation
├── models.py              # Feedback dataclass
├── audio.py               # say/ffmpeg/whisper-cli subprocess wrappers
├── claude_client.py       # Claude Agent SDK wrapper (stateless queries)
├── orchestrator.py        # per-chat state machine, round emission
├── poller.py              # python-telegram-bot Application + handlers
└── prompts/
    └── system.md          # Claude system prompt (ported from skill)

tests/
├── conftest.py            # shared fixtures
├── fixtures/
│   └── sample_voice.wav   # 16kHz mono, short clear English sentence
├── test_config.py
├── test_models.py
├── test_audio_integration.py
├── test_claude_client.py
├── test_orchestrator.py
├── test_poller_whitelist.py
└── smoke.md               # manual end-to-end checklist

scripts/run_bot.sh         # venv activate + python -m english_bot
pyproject.toml             # deps + tool config
.env.example               # env vars template
.gitignore                 # updated (venv, .env, __pycache__)
```

Each module has one responsibility (see spec §Components). Tests mirror module names.

---

## Task 1: Project scaffolding (no tests — setup only)

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `english_bot/__init__.py` (empty)
- Create: `english_bot/prompts/.gitkeep` (placeholder)
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py` (skeleton)
- Modify: `.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "english-bot"
version = "0.1.0"
description = "Telegram bot for English speaking practice (personal use, macOS only)"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot[ext]>=21.0,<22.0",
    "claude-agent-sdk",
    "python-dotenv>=1.0,<2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["english_bot*"]

[tool.setuptools.package-data]
english_bot = ["prompts/*.md"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write `.env.example`**

```
TELEGRAM_BOT_TOKEN=
ALLOWED_CHAT_IDS=123456789,987654321
WHISPER_MODEL=/Users/vuongluu/.cache/whisper-cpp/ggml-small.en.bin
SPEAK_VOICE=Linh (Enhanced)
SPEAK_EN_VOICE=Samantha
LOG_LEVEL=INFO
```

- [ ] **Step 3: Update `.gitignore`**

Append (do not replace existing entries):
```
# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/

# Local secrets
.env
```

- [ ] **Step 4: Create empty package files**

```bash
touch english_bot/__init__.py
mkdir -p english_bot/prompts && touch english_bot/prompts/.gitkeep
mkdir -p tests/fixtures && touch tests/__init__.py
```

- [ ] **Step 5: Write `tests/conftest.py` skeleton**

```python
"""Shared pytest fixtures for english_bot tests."""
```

- [ ] **Step 6: Create venv + install**

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```
Expected: install completes, no errors.

- [ ] **Step 7: Verify scaffolding**

```bash
.venv/bin/pytest --collect-only
```
Expected: "no tests ran" (no tests yet — that's fine).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .env.example .gitignore english_bot/ tests/
git commit -m "feat(bot): scaffold Python package + dev environment"
```

---

## Task 2: `config.py` — env loading with fail-fast

**Files:**
- Create: `english_bot/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
import os
import pytest
from english_bot.config import Config, ConfigError


def test_loads_all_env_vars(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc:xyz")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "100,200,300")
    monkeypatch.setenv("WHISPER_MODEL", "/tmp/model.bin")
    monkeypatch.setenv("SPEAK_VOICE", "Linh (Enhanced)")
    monkeypatch.setenv("SPEAK_EN_VOICE", "Samantha")
    cfg = Config.from_env()
    assert cfg.telegram_token == "abc:xyz"
    assert cfg.allowed_chat_ids == {100, 200, 300}
    assert cfg.whisper_model == "/tmp/model.bin"
    assert cfg.speak_voice == "Linh (Enhanced)"
    assert cfg.speak_en_voice == "Samantha"
    assert cfg.log_level == "INFO"  # default


def test_missing_telegram_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "1")
    monkeypatch.setenv("WHISPER_MODEL", "/tmp/m")
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        Config.from_env()


def test_empty_allowed_chat_ids_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "")
    monkeypatch.setenv("WHISPER_MODEL", "/tmp/m")
    with pytest.raises(ConfigError, match="ALLOWED_CHAT_IDS"):
        Config.from_env()


def test_non_integer_chat_id_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "100,not_a_number")
    monkeypatch.setenv("WHISPER_MODEL", "/tmp/m")
    with pytest.raises(ConfigError, match="invalid chat_id"):
        Config.from_env()


def test_defaults_for_voice_vars(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "1")
    monkeypatch.setenv("WHISPER_MODEL", "/tmp/m")
    monkeypatch.delenv("SPEAK_VOICE", raising=False)
    monkeypatch.delenv("SPEAK_EN_VOICE", raising=False)
    cfg = Config.from_env()
    assert cfg.speak_voice == "Linh (Enhanced)"
    assert cfg.speak_en_voice == "Samantha"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_config.py -v
```
Expected: ImportError (no `english_bot.config` yet).

- [ ] **Step 3: Implement `english_bot/config.py`**

```python
"""Environment configuration with fail-fast validation."""
import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when required env vars are missing or invalid."""


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_chat_ids: frozenset[int]
    whisper_model: str
    speak_voice: str
    speak_en_voice: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ConfigError("TELEGRAM_BOT_TOKEN is required")

        raw_ids = os.environ.get("ALLOWED_CHAT_IDS", "").strip()
        if not raw_ids:
            raise ConfigError(
                "ALLOWED_CHAT_IDS is required (comma-separated chat IDs)"
            )
        try:
            ids = frozenset(int(x.strip()) for x in raw_ids.split(",") if x.strip())
        except ValueError as e:
            raise ConfigError(f"invalid chat_id in ALLOWED_CHAT_IDS: {e}") from e
        if not ids:
            raise ConfigError("ALLOWED_CHAT_IDS must contain at least one ID")

        whisper_model = os.environ.get("WHISPER_MODEL", "").strip()
        if not whisper_model:
            raise ConfigError("WHISPER_MODEL path is required")

        return cls(
            telegram_token=token,
            allowed_chat_ids=ids,
            whisper_model=whisper_model,
            speak_voice=os.environ.get("SPEAK_VOICE", "").strip() or "Linh (Enhanced)",
            speak_en_voice=os.environ.get("SPEAK_EN_VOICE", "").strip() or "Samantha",
            log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_config.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add english_bot/config.py tests/test_config.py
git commit -m "feat(bot): config loader with fail-fast env validation"
```

---

## Task 3: `models.py` — `Feedback` dataclass + JSON parsing

**Files:**
- Create: `english_bot/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

`tests/test_models.py`:
```python
import pytest
from english_bot.models import Feedback, FeedbackParseError


def test_feedback_from_json_happy_path():
    payload = '''
    {
      "transcript": "I have been working here for 3 years",
      "evaluation_text": "Cấu trúc đúng, dùng present perfect continuous tốt.",
      "model_english": "I have been working here for three years.",
      "vi_summary": "Dùng `have been working` chuẩn rồi đó. Câu tiếp theo."
    }
    '''
    fb = Feedback.from_json(payload)
    assert fb.transcript.startswith("I have been")
    assert fb.model_english.startswith("I have been")
    assert "have been working" in fb.vi_summary


def test_feedback_from_json_missing_field_raises():
    payload = '{"transcript": "x", "evaluation_text": "y", "model_english": "z"}'
    with pytest.raises(FeedbackParseError, match="vi_summary"):
        Feedback.from_json(payload)


def test_feedback_from_json_malformed_raises():
    with pytest.raises(FeedbackParseError, match="JSON"):
        Feedback.from_json("not json at all")


def test_feedback_from_json_extracts_from_code_fence():
    # Claude often wraps JSON in ```json ... ``` fences. Strip them.
    payload = '''```json
    {"transcript": "a", "evaluation_text": "b", "model_english": "c", "vi_summary": "d"}
    ```'''
    fb = Feedback.from_json(payload)
    assert fb.transcript == "a"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_models.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `english_bot/models.py`**

```python
"""Data models for the bot."""
import json
import re
from dataclasses import dataclass


class FeedbackParseError(ValueError):
    """Raised when Claude's feedback payload is not valid JSON or is missing fields."""


@dataclass(frozen=True)
class Feedback:
    transcript: str
    evaluation_text: str
    model_english: str
    vi_summary: str

    @classmethod
    def from_json(cls, payload: str) -> "Feedback":
        text = _strip_code_fence(payload).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise FeedbackParseError(f"invalid JSON: {e}") from e
        try:
            return cls(
                transcript=data["transcript"],
                evaluation_text=data["evaluation_text"],
                model_english=data["model_english"],
                vi_summary=data["vi_summary"],
            )
        except KeyError as e:
            raise FeedbackParseError(f"missing field: {e.args[0]}") from e


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    m = _FENCE_RE.match(text)
    return m.group(1) if m else text
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_models.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add english_bot/models.py tests/test_models.py
git commit -m "feat(bot): Feedback dataclass with JSON parsing + code-fence stripping"
```

---

## Task 4: `prompts/system.md` — Claude system prompt

No tests for this file — content review only. It defines the contract for `claude_client`. Code-fence handling tested in Task 3.

**Files:**
- Create: `english_bot/prompts/system.md`

- [ ] **Step 1: Write `english_bot/prompts/system.md`**

```markdown
# English Practice Coach (Telegram bot)

Bạn là English speaking coach cho 1 Vietnamese fullstack dev qua Telegram. Không tương tác như chat — mỗi câu user gửi tới bạn là 1 query độc lập (stateless). Tuỳ tool, bạn có 2 nhiệm vụ rời nhau: **(A)** sinh 1 câu Vi để user nói English, hoặc **(B)** đánh giá transcript user vừa nói. Bạn KHÔNG gọi Bash, KHÔNG dùng tools — chỉ trả về text/JSON theo định dạng yêu cầu.

---

## Nhiệm vụ A — Sinh câu prompt tiếng Việt

Khi user request "Sinh 1 câu":

- Câu Việt conversational, độ dài 8-18 từ.
- Chủ đề ngẫu nhiên, đa dạng tối đa: chuyện đời thường, công việc dev, du lịch, ăn uống, gia đình, ý kiến cá nhân, kể chuyện, smalltalk, mua sắm online, sửa đồ trong nhà, lý do từ chối lời mời, hobby ngách, tin tức nhẹ, v.v. KHÔNG giới hạn ở danh sách cố định.
- Đủ thử thách: bao 1 cấu trúc/idiom không trivial (phrasal verb, conditional, present perfect, relative clause…).
- KHÔNG quá học thuật. KHÔNG dịch máy.
- ✅ Tốt: "Sếp tôi vừa bảo dời cuộc họp sang chiều mai vì khách hàng bận."
- ❌ Tránh: "Hôm nay tôi đi học." (quá đơn giản)
- **Bọc mọi từ/cụm tiếng Anh trong backticks** — vd: "Hôm nay tôi có `meeting` về `deadline` mới." Để TTS bilingual đọc chuẩn (Linh đọc Vi, Samantha đọc English trong backticks). Không bọc tên riêng đã Việt hoá ("Sài Gòn", "Hà Nội").

**Format trả về:** chỉ duy nhất 1 dòng — câu Vi đó. KHÔNG markdown, KHÔNG quotes bao quanh, KHÔNG giải thích.

---

## Nhiệm vụ B — Đánh giá transcript

Khi user cung cấp:
- `Vi prompt`: câu Vi đã đưa.
- `English transcript`: câu user nói lại bằng English (từ Whisper STT, có thể có lỗi nghe).

Trả về **chỉ 1 JSON object** (không markdown fence, không text ngoài JSON) với 4 fields:

```json
{
  "transcript": "<echo lại transcript user>",
  "evaluation_text": "<text feedback chi tiết — hiển thị trên Telegram dưới dạng text. 3-6 dòng. Bao gồm: ✅ Model (câu English tự nhiên nhất), 📝 Feedback bullets (grammar/usage), 🔊 Pronunciation note nếu có signal cụ thể>",
  "model_english": "<câu English tự nhiên nhất cho prompt Vi đó. Plain text, 1 câu, sẽ được TTS đọc bằng Samantha rate 140>",
  "vi_summary": "<feedback Vi 3-5 câu sẽ được TTS đọc to. Bọc English trong backticks. Kết thúc bằng 'Câu tiếp theo.'>"
}
```

### Quy tắc cho `evaluation_text`:

Format Markdown-ready (Telegram MarkdownV2 sẽ escape sau):
```
🎙️ You said: <transcript>
✅ Model: <model_english>

📝 Feedback:
• <điểm 1>
• <điểm 2 — nếu có>

🔊 Pronunciation: <chỉ note nếu có signal>
```

- Transcript đúng/gần đúng Model → khen ngắn ("Nice, natural!"), không bullet thừa.
- Sai grammar nhẹ (article, preposition) → 1 bullet + giải thích why.
- Sai cấu trúc lớn (sai thì, sai chủ ngữ) → 1-2 bullet, gợi ý cách nghĩ lại.
- Transcript là bản dịch tự nhiên KHÁC nhưng đúng nghĩa → công nhận ("Cả 2 cách đều ổn!"), đưa Model như alternative.

### Pronunciation note — CHỈ thêm khi có signal:

| Signal trong transcript | Inference | Note |
|---|---|---|
| Whisper thiếu hẳn 1 từ quan trọng | Phát âm yếu chữ đó | "X" /IPA/ — cách đặt miệng |
| Whisper ra từ rất khác (vd "tree" → "three", "thought" → "taught") | Nhầm âm vị (/θ/ vs /t/) | Chỉ ra âm vị + cách tạo âm |
| Thiếu ending consonant ("want" → "wan") | Endings yếu | "Nhớ nhả âm cuối /t/" |

KHÔNG thêm note nếu Whisper transcribe sạch, hoặc lỗi chỉ là grammar.

### Quy tắc cho `vi_summary`:

- 3-5 câu Vi, ngắn gọn, conversational.
- **Bọc mọi English trong backticks** để Samantha đọc chuẩn.
- Bao gồm: đánh giá ngắn + nhắc lại model phrase trong backticks + giải thích why + tip phát âm nếu có.
- Kết thúc đúng cụm: `Câu tiếp theo.`
- Nếu user gần đúng → 2-3 câu khen + nhắc model phrase bằng English, vẫn đủ thông tin (không cụt lủn).

Ví dụ:
> "Câu bạn nói khá ổn rồi, chỉ thiếu present perfect. Thay vì `I work here for 3 years`, dùng `I have been working here for 3 years` — present perfect continuous diễn tả hành động bắt đầu trong quá khứ và còn tiếp diễn. Phát âm `been` hơi yếu, nhớ kéo dài âm `ee`. Câu tiếp theo."

---

## Quan trọng

- Không thêm preamble như "Đây là câu của bạn:". Trả thẳng output yêu cầu.
- JSON output (Nhiệm vụ B) phải parse được bằng `json.loads()`. Nếu cần dấu nháy kép trong text, escape `\"`.
- KHÔNG trả về cả 2 nhiệm vụ trong 1 query — mỗi query chỉ làm A hoặc B.
```

- [ ] **Step 2: Verify file exists and renders**

```bash
ls -l english_bot/prompts/system.md
wc -l english_bot/prompts/system.md
```
Expected: file present, ~60-80 lines.

- [ ] **Step 3: Commit**

```bash
git add english_bot/prompts/system.md
git rm --cached english_bot/prompts/.gitkeep 2>/dev/null || true
rm -f english_bot/prompts/.gitkeep
git add -u
git commit -m "feat(bot): port English-practice skill prompt to Claude system prompt"
```

---

## Task 5: `audio.py` part 1 — `synthesize_en` (single-voice TTS to ogg)

This is the simplest audio function — no bilingual split. Establishes the `say + ffmpeg` subprocess pipeline.

**Files:**
- Create: `english_bot/audio.py`
- Create: `tests/test_audio_integration.py`

- [ ] **Step 1: Write failing test**

`tests/test_audio_integration.py`:
```python
"""Integration tests — require macOS `say`, `ffmpeg`, `whisper-cli` on PATH."""
import shutil
import subprocess
from pathlib import Path

import pytest

from english_bot.audio import synthesize_en

requires_macos_audio = pytest.mark.skipif(
    not (shutil.which("say") and shutil.which("ffmpeg")),
    reason="requires macOS `say` and `ffmpeg`",
)


@requires_macos_audio
def test_synthesize_en_produces_valid_ogg(tmp_path):
    out = synthesize_en("Hello world, this is a test.", tmp_path, voice="Samantha")
    assert out.exists()
    assert out.suffix == ".ogg"
    # ffprobe duration > 0
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    assert duration > 0.3  # at least some content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_audio_integration.py::test_synthesize_en_produces_valid_ogg -v
```
Expected: ImportError (`english_bot.audio` doesn't exist).

- [ ] **Step 3: Implement `synthesize_en` in `english_bot/audio.py`**

```python
"""Subprocess wrappers for macOS audio I/O.

Pipeline:
  - synthesize_en/vi: `say -o aiff` → `ffmpeg → ogg/opus` (Telegram-friendly)
  - transcribe: incoming ogg → `ffmpeg → 16kHz mono wav` → `whisper-cli` → text

No live mic capture (Telegram delivers pre-recorded voice notes), so sox/rec
is NOT used here. The terminal scripts `speak.sh` and `record.sh` stay
untouched for the slash-command flow.
"""
import subprocess
from pathlib import Path


class AudioError(RuntimeError):
    """Raised when an audio subprocess fails."""


def synthesize_en(text: str, work_dir: Path, voice: str = "Samantha",
                  rate: int = 140) -> Path:
    """Render plain English to an Opus-in-OGG file using macOS `say` + ffmpeg.

    Args:
        text: English text to synthesize (no backtick splitting).
        work_dir: existing directory for intermediate + output files.
        voice: macOS voice name (default Samantha).
        rate: words per minute (default 140 — slow for listening practice).

    Returns:
        Path to the .ogg file inside work_dir.
    """
    aiff_path = work_dir / "en.aiff"
    ogg_path = work_dir / "en.ogg"
    _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff_path), text])
    _aiff_to_ogg(aiff_path, ogg_path)
    return ogg_path


def _aiff_to_ogg(aiff_path: Path, ogg_path: Path) -> None:
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(aiff_path),
        "-c:a", "libopus", "-b:a", "48k",
        str(ogg_path),
    ])


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AudioError(
            f"{cmd[0]} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_audio_integration.py::test_synthesize_en_produces_valid_ogg -v
```
Expected: PASS (or SKIPPED on non-macOS — that's OK, this only runs on the dev box).

- [ ] **Step 5: Commit**

```bash
git add english_bot/audio.py tests/test_audio_integration.py
git commit -m "feat(bot): audio.synthesize_en — say + ffmpeg → ogg/opus"
```

---

## Task 6: `audio.py` part 2 — `synthesize_vi` with bilingual backtick split

Mirrors the logic in `scripts/speak.sh` (bilingual Vi/En with backticks), but writes to file and concats via ffmpeg.

**Files:**
- Modify: `english_bot/audio.py`
- Modify: `tests/test_audio_integration.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_audio_integration.py`:
```python
from english_bot.audio import synthesize_vi, _split_backticks


def test_split_backticks_alternates():
    parts = _split_backticks("Hôm nay tôi có `meeting` về `deadline` mới.")
    # Returns list[(is_english, text)]
    assert parts == [
        (False, "Hôm nay tôi có"),
        (True, "meeting"),
        (False, "về"),
        (True, "deadline"),
        (False, "mới."),
    ]


def test_split_backticks_no_english():
    parts = _split_backticks("Câu thuần Việt không có backticks.")
    assert parts == [(False, "Câu thuần Việt không có backticks.")]


def test_split_backticks_strips_whitespace_only_chunks():
    parts = _split_backticks("`hello`")
    assert parts == [(True, "hello")]


@requires_macos_audio
def test_synthesize_vi_bilingual_produces_ogg(tmp_path):
    text = "Hôm nay tôi có `meeting` về `deadline` mới."
    out = synthesize_vi(text, tmp_path, vi_voice="Linh", en_voice="Samantha", rate=170)
    assert out.exists()
    assert out.suffix == ".ogg"
    # Concat result should be > sum of individual chunk minimum durations
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    assert duration > 1.0  # multi-chunk Vi+En sentence


@requires_macos_audio
def test_synthesize_vi_pure_vietnamese_no_concat(tmp_path):
    out = synthesize_vi("Xin chào, hôm nay trời đẹp quá.", tmp_path,
                        vi_voice="Linh", en_voice="Samantha", rate=170)
    assert out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_audio_integration.py -v
```
Expected: pure-Python tests fail with ImportError; integration tests fail with `synthesize_vi` undefined.

- [ ] **Step 3: Extend `english_bot/audio.py`**

Append:
```python
def synthesize_vi(text: str, work_dir: Path, vi_voice: str = "Linh (Enhanced)",
                  en_voice: str = "Samantha", rate: int = 170) -> Path:
    """Render Vi text with `english` backtick-bracketed chunks read by en_voice.

    Bilingual split: text outside backticks → vi_voice; text inside → en_voice.
    Each chunk is `say -o` to its own aiff, converted to ogg, then concatenated
    via ffmpeg into one final ogg. If only one chunk exists, no concat.
    """
    chunks = _split_backticks(text)
    if not chunks:
        raise AudioError("synthesize_vi got empty text")

    if len(chunks) == 1:
        is_en, chunk_text = chunks[0]
        voice = en_voice if is_en else _resolve_vi_voice(vi_voice)
        aiff = work_dir / "vi.aiff"
        ogg = work_dir / "vi.ogg"
        _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), chunk_text])
        _aiff_to_ogg(aiff, ogg)
        return ogg

    ogg_parts: list[Path] = []
    for i, (is_en, chunk_text) in enumerate(chunks):
        voice = en_voice if is_en else _resolve_vi_voice(vi_voice)
        aiff = work_dir / f"vi_{i}.aiff"
        ogg = work_dir / f"vi_{i}.ogg"
        _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), chunk_text])
        _aiff_to_ogg(aiff, ogg)
        ogg_parts.append(ogg)

    return _concat_oggs(ogg_parts, work_dir / "vi.ogg")


def _split_backticks(text: str) -> list[tuple[bool, str]]:
    """Split on backticks. Returns [(is_english, chunk)]. Trims whitespace,
    skips empty chunks. Odd-indexed parts (after split) are English."""
    parts = text.split("`")
    out: list[tuple[bool, str]] = []
    for i, raw in enumerate(parts):
        chunk = raw.strip()
        if not chunk:
            continue
        out.append((i % 2 == 1, chunk))
    return out


def _resolve_vi_voice(requested: str) -> str:
    """If the requested Vi voice (Enhanced) is not installed, fall back to plain Linh.

    Mirrors the fallback logic in scripts/speak.sh.
    """
    try:
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return "Linh"
    voices = result.stdout
    # match "Linh (Enhanced)" only if it appears as a voice name line prefix.
    if any(line.startswith(requested) for line in voices.splitlines()):
        return requested
    return "Linh"


def _concat_oggs(parts: list[Path], out_path: Path) -> Path:
    """Use ffmpeg concat demuxer to join multiple oggs in order."""
    listfile = out_path.with_suffix(".list")
    listfile.write_text("".join(f"file '{p}'\n" for p in parts))
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(listfile),
        "-c", "copy",
        str(out_path),
    ])
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_audio_integration.py -v
```
Expected: pure-Python tests PASS; integration tests PASS on macOS dev box (or SKIPPED elsewhere).

- [ ] **Step 5: Commit**

```bash
git add english_bot/audio.py tests/test_audio_integration.py
git commit -m "feat(bot): audio.synthesize_vi — bilingual backtick split + ffmpeg concat"
```

---

## Task 7: `audio.py` part 3 — `transcribe` (ogg → whisper-cli → text)

**Files:**
- Modify: `english_bot/audio.py`
- Modify: `tests/test_audio_integration.py`
- Create: `tests/fixtures/sample_voice.wav` (16kHz mono, ~2-3 sec of clear English)

- [ ] **Step 1: Create fixture audio file**

```bash
# Use macOS `say` to generate a deterministic test fixture.
say -v Samantha -r 150 -o /tmp/_fix.aiff "The quick brown fox jumps over the lazy dog."
ffmpeg -y -loglevel error -i /tmp/_fix.aiff -ac 1 -ar 16000 tests/fixtures/sample_voice.wav
rm /tmp/_fix.aiff
ls -lh tests/fixtures/sample_voice.wav
```
Expected: a small wav file (~70-150 KB).

- [ ] **Step 2: Add failing test**

Append to `tests/test_audio_integration.py`:
```python
import os
from english_bot.audio import transcribe

requires_whisper = pytest.mark.skipif(
    not shutil.which("whisper-cli") or not os.environ.get("WHISPER_MODEL"),
    reason="requires whisper-cli on PATH and WHISPER_MODEL env",
)


@requires_macos_audio
@requires_whisper
def test_transcribe_returns_sensible_text(tmp_path):
    # Copy fixture into work_dir so transcribe path mirrors real usage
    src = Path("tests/fixtures/sample_voice.wav")
    work = tmp_path / "in.wav"
    work.write_bytes(src.read_bytes())

    transcript = transcribe(work, model_path=os.environ["WHISPER_MODEL"])
    lower = transcript.lower()
    # Tolerate Whisper quirks but expect key content words.
    assert "fox" in lower or "brown" in lower
    assert "lazy" in lower or "dog" in lower


@requires_macos_audio
@requires_whisper
def test_transcribe_ogg_input_is_converted(tmp_path):
    # Synthesize a small ogg then transcribe it
    ogg = synthesize_en("Testing one two three.", tmp_path, voice="Samantha", rate=160)
    transcript = transcribe(ogg, model_path=os.environ["WHISPER_MODEL"])
    assert "testing" in transcript.lower() or "one" in transcript.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_audio_integration.py -v -k transcribe
```
Expected: ImportError (`transcribe` undefined).

- [ ] **Step 4: Extend `english_bot/audio.py`**

Append:
```python
def transcribe(audio_path: Path, model_path: str) -> str:
    """Transcribe an audio file (ogg, wav, m4a…) to English text via whisper-cli.

    Converts the input to 16kHz mono wav via ffmpeg, then runs whisper-cli with
    the given model. Returns the trimmed transcript (may be empty string if
    nothing was detected).
    """
    work_dir = audio_path.parent
    wav_path = work_dir / "_whisper_in.wav"
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(audio_path),
        "-ac", "1", "-ar", "16000",
        str(wav_path),
    ])
    out_prefix = work_dir / "_whisper_out"
    # whisper-cli writes <prefix>.txt containing the transcript.
    _run([
        "whisper-cli",
        "-m", model_path,
        "-f", str(wav_path),
        "-otxt",
        "-of", str(out_prefix),
        "-nt",       # no timestamps
        "-l", "en",  # force English
    ])
    txt_path = out_prefix.with_suffix(".txt")
    if not txt_path.exists():
        raise AudioError(f"whisper-cli produced no output: {txt_path}")
    return txt_path.read_text(encoding="utf-8").strip()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_audio_integration.py -v
```
Expected: all audio tests PASS (or SKIP cleanly on non-macOS).

- [ ] **Step 6: Commit**

```bash
git add english_bot/audio.py tests/test_audio_integration.py tests/fixtures/sample_voice.wav
git commit -m "feat(bot): audio.transcribe — ffmpeg → 16k mono wav → whisper-cli"
```

---

## Task 8: `claude_client.py` — Claude Agent SDK wrapper

Stateless: each call creates a fresh `ClaudeSDKClient`. Two functions: `generate_prompt()` (Nhiệm vụ A in system.md) and `evaluate()` (Nhiệm vụ B).

**Files:**
- Create: `english_bot/claude_client.py`
- Create: `tests/test_claude_client.py`

- [ ] **Step 1: Investigate claude-agent-sdk API surface**

Before writing tests, confirm the SDK call shape. Either inspect installed package or fetch docs.

```bash
.venv/bin/python -c "import claude_agent_sdk; help(claude_agent_sdk)" | head -80
```

Document the chosen entry point (typically `ClaudeSDKClient` or a `query()` function) inline in the module docstring. The wrapper isolates the choice so the rest of the bot doesn't depend on SDK shape.

- [ ] **Step 2: Write failing tests (mocking the SDK)**

`tests/test_claude_client.py`:
```python
import json
from unittest.mock import AsyncMock, patch

import pytest

from english_bot.claude_client import ClaudeClient
from english_bot.models import Feedback, FeedbackParseError


@pytest.fixture
def system_prompt(tmp_path):
    p = tmp_path / "system.md"
    p.write_text("# Test system prompt")
    return p


async def test_generate_prompt_returns_stripped_single_line(system_prompt):
    client = ClaudeClient(system_prompt_path=system_prompt)
    with patch.object(client, "_query", new=AsyncMock(return_value="  Hôm nay tôi có `meeting` mới.  \n")):
        result = await client.generate_prompt()
    assert result == "Hôm nay tôi có `meeting` mới."


async def test_evaluate_returns_feedback(system_prompt):
    payload = json.dumps({
        "transcript": "I work here for 3 years",
        "evaluation_text": "🎙️ You said: ...",
        "model_english": "I have been working here for three years.",
        "vi_summary": "Dùng `have been working`. Câu tiếp theo.",
    })
    client = ClaudeClient(system_prompt_path=system_prompt)
    with patch.object(client, "_query", new=AsyncMock(return_value=payload)):
        fb = await client.evaluate("Tôi làm ở đây 3 năm.", "I work here for 3 years")
    assert isinstance(fb, Feedback)
    assert "have been working" in fb.vi_summary


async def test_evaluate_malformed_json_raises(system_prompt):
    client = ClaudeClient(system_prompt_path=system_prompt)
    with patch.object(client, "_query", new=AsyncMock(return_value="not json")):
        with pytest.raises(FeedbackParseError):
            await client.evaluate("vi", "en")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_claude_client.py -v
```
Expected: ImportError.

- [ ] **Step 4: Implement `english_bot/claude_client.py`**

```python
"""Stateless Claude Agent SDK wrapper.

Each public method creates a fresh query — no session reuse. The bot is
stateless per round (see spec §Architecture).

The exact SDK call shape is centralised in `_query()`. If the SDK API
changes, edit only that method. Callers depend on string in / string out.
"""
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from english_bot.models import Feedback


class ClaudeClient:
    def __init__(self, system_prompt_path: Path):
        self._system_prompt = system_prompt_path.read_text(encoding="utf-8")

    async def generate_prompt(self) -> str:
        """Nhiệm vụ A — return a fresh Vietnamese sentence (single line)."""
        user = "Sinh 1 câu (Nhiệm vụ A). Trả về duy nhất câu Vi, không quotes, không giải thích."
        raw = await self._query(user)
        return raw.strip().splitlines()[0].strip() if raw.strip() else ""

    async def evaluate(self, vi_prompt: str, transcript: str) -> Feedback:
        """Nhiệm vụ B — evaluate the user's English transcript against the Vi prompt."""
        user = (
            "Nhiệm vụ B. Đánh giá transcript dưới đây.\n\n"
            f"Vi prompt: {vi_prompt}\n"
            f"English transcript: {transcript}\n\n"
            "Trả về JSON duy nhất, đúng schema 4 fields."
        )
        raw = await self._query(user)
        return Feedback.from_json(raw)

    async def _query(self, user_message: str) -> str:
        """Single fresh stateless query to Claude.

        Returns the model's text response (concatenation of text blocks).
        """
        options = ClaudeAgentOptions(system_prompt=self._system_prompt)
        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_message)
            chunks: list[str] = []
            async for msg in client.receive_response():
                # ResultMessage has `.result`; AssistantMessage has `.content`
                # Adapt to the SDK's emitted shapes; collect any textual blocks.
                if hasattr(msg, "content"):
                    for block in msg.content:
                        text = getattr(block, "text", None)
                        if text:
                            chunks.append(text)
                elif hasattr(msg, "result") and isinstance(msg.result, str):
                    chunks.append(msg.result)
            return "".join(chunks).strip()
```

> **Note for the implementer:** The exact `claude_agent_sdk` API may differ between SDK versions. Inspect the installed package (`.venv/bin/python -c "from claude_agent_sdk import *; ..."`) to confirm `ClaudeSDKClient`, `ClaudeAgentOptions`, and the iteration protocol. Adjust `_query()` accordingly — keep its signature (`str -> str`) stable. If the SDK auto-discovers Claude.ai login via `~/.claude/` credentials (it does as of recent versions), no explicit auth needed.

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_claude_client.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add english_bot/claude_client.py tests/test_claude_client.py
git commit -m "feat(bot): claude_client — stateless Claude Agent SDK wrapper"
```

---

## Task 9: `orchestrator.py` — per-chat state machine

The brain. Drives `/start` → round → wait for voice → evaluate → emit next round. `/stop` halts the loop.

**Files:**
- Create: `english_bot/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

`tests/test_orchestrator.py`:
```python
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from english_bot.models import Feedback
from english_bot.orchestrator import ChatState, Orchestrator


@pytest.fixture
def fake_claude():
    c = MagicMock()
    c.generate_prompt = AsyncMock(return_value="Hôm nay tôi có `meeting` mới.")
    c.evaluate = AsyncMock(return_value=Feedback(
        transcript="I have a meeting today",
        evaluation_text="🎙️ ...",
        model_english="I have a meeting today.",
        vi_summary="Tốt rồi đó. Câu tiếp theo.",
    ))
    return c


@pytest.fixture
def fake_audio(tmp_path):
    a = MagicMock()
    a.synthesize_vi = MagicMock(return_value=tmp_path / "vi.ogg")
    a.synthesize_en = MagicMock(return_value=tmp_path / "en.ogg")
    a.transcribe = MagicMock(return_value="I have a meeting today")
    return a


@pytest.fixture
def fake_sender():
    s = MagicMock()
    s.send_text = AsyncMock()
    s.send_voice = AsyncMock()
    return s


async def test_begin_session_emits_round_and_waits_for_voice(
    fake_claude, fake_audio, fake_sender, tmp_path,
):
    orch = Orchestrator(
        claude=fake_claude,
        audio=fake_audio,
        sender=fake_sender,
        whisper_model="/tmp/m",
        vi_voice="Linh",
        en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    assert orch.state_of(42) == ChatState.WAITING_VOICE
    fake_claude.generate_prompt.assert_awaited_once()
    fake_sender.send_text.assert_awaited()           # Vi text prompt
    fake_sender.send_voice.assert_awaited()          # Vi voice prompt
    fake_audio.synthesize_vi.assert_called_once()


async def test_voice_reply_triggers_feedback_and_next_round(
    fake_claude, fake_audio, fake_sender, tmp_path,
):
    orch = Orchestrator(
        claude=fake_claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    fake_claude.generate_prompt.reset_mock()
    fake_sender.send_text.reset_mock()
    fake_sender.send_voice.reset_mock()
    fake_audio.synthesize_vi.reset_mock()

    await orch.handle_voice(chat_id=42, voice_path=tmp_path / "user.ogg")

    fake_audio.transcribe.assert_called_once()
    fake_claude.evaluate.assert_awaited_once()
    # Feedback text + model voice + Vi summary voice
    assert fake_sender.send_text.await_count >= 1
    assert fake_sender.send_voice.await_count >= 2
    # Next round emitted
    fake_claude.generate_prompt.assert_awaited_once()
    assert orch.state_of(42) == ChatState.WAITING_VOICE


async def test_stop_halts_emit_next_round(fake_claude, fake_audio, fake_sender, tmp_path):
    orch = Orchestrator(
        claude=fake_claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    orch.stop(chat_id=42)
    assert orch.state_of(42) == ChatState.STOPPED


async def test_voice_when_idle_replies_hint(fake_claude, fake_audio, fake_sender, tmp_path):
    orch = Orchestrator(
        claude=fake_claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    # No begin_session — chat is IDLE
    await orch.handle_voice(chat_id=42, voice_path=tmp_path / "x.ogg")
    fake_audio.transcribe.assert_not_called()
    fake_claude.evaluate.assert_not_awaited()
    fake_sender.send_text.assert_awaited_with(42, msg_match="start")


async def test_begin_session_idempotent_when_already_running(
    fake_claude, fake_audio, fake_sender, tmp_path,
):
    orch = Orchestrator(
        claude=fake_claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    fake_claude.generate_prompt.reset_mock()
    await orch.begin_session(chat_id=42)  # second /start
    fake_claude.generate_prompt.assert_not_awaited()  # no new round
```

> **Helper:** `send_text.assert_awaited_with(42, msg_match=...)` is shorthand — replace with the real assertion style your `Sender` interface needs. Adjust during implementation.

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_orchestrator.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `english_bot/orchestrator.py`**

```python
"""Per-chat state machine driving the Vi prompt → Eng answer → feedback loop."""
import logging
import tempfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Protocol

from english_bot.audio import AudioError
from english_bot.claude_client import ClaudeClient
from english_bot.models import Feedback, FeedbackParseError

log = logging.getLogger(__name__)


class ChatState(Enum):
    IDLE = auto()
    WAITING_VOICE = auto()
    STOPPED = auto()


class Sender(Protocol):
    """Minimal interface the orchestrator needs from the Telegram layer."""
    async def send_text(self, chat_id: int, text: str) -> None: ...
    async def send_voice(self, chat_id: int, voice_path: Path) -> None: ...


@dataclass
class _Session:
    state: ChatState
    last_vi_prompt: str = ""


class Orchestrator:
    def __init__(
        self,
        claude: ClaudeClient,
        audio,                # english_bot.audio module (or compatible)
        sender: Sender,
        whisper_model: str,
        vi_voice: str,
        en_voice: str,
        work_dir_factory: Callable[[], Path] | None = None,
    ):
        self._claude = claude
        self._audio = audio
        self._sender = sender
        self._whisper_model = whisper_model
        self._vi_voice = vi_voice
        self._en_voice = en_voice
        self._sessions: dict[int, _Session] = {}
        self._work_dir_factory = work_dir_factory

    def state_of(self, chat_id: int) -> ChatState:
        s = self._sessions.get(chat_id)
        return s.state if s else ChatState.IDLE

    async def begin_session(self, chat_id: int) -> None:
        existing = self._sessions.get(chat_id)
        if existing and existing.state == ChatState.WAITING_VOICE:
            await self._sender.send_text(
                chat_id, "Session đang chạy. Gõ /stop để dừng trước."
            )
            return
        self._sessions[chat_id] = _Session(state=ChatState.WAITING_VOICE)
        await self._emit_round(chat_id)

    def stop(self, chat_id: int) -> None:
        if chat_id in self._sessions:
            self._sessions[chat_id] = _Session(state=ChatState.STOPPED)

    async def handle_voice(self, chat_id: int, voice_path: Path) -> None:
        session = self._sessions.get(chat_id)
        if not session or session.state != ChatState.WAITING_VOICE:
            await self._sender.send_text(
                chat_id, "Gõ /start để bắt đầu session luyện English."
            )
            return

        try:
            transcript = self._audio.transcribe(voice_path, model_path=self._whisper_model)
        except AudioError as e:
            log.warning("transcribe failed (chat=%s): %s", chat_id, e)
            await self._sender.send_text(chat_id, "Lỗi xử lý voice, thử lại.")
            return

        if not transcript:
            await self._sender.send_text(chat_id, "Không nghe rõ, thử lại.")
            return

        try:
            feedback = await self._claude.evaluate(session.last_vi_prompt, transcript)
        except FeedbackParseError as e:
            log.warning("feedback parse failed (chat=%s): %s", chat_id, e)
            await self._sender.send_text(
                chat_id, f"Feedback format lạ, lưu lại:\n{e}"
            )
            # advance anyway — don't stick
        except Exception as e:
            log.warning("claude.evaluate failed (chat=%s): %s", chat_id, e)
            await self._sender.send_text(chat_id, "Claude busy, thử lại sau vài giây.")
            return  # keep state WAITING_VOICE so user can retry
        else:
            await self._deliver_feedback(chat_id, feedback)

        # check we weren't stopped mid-call
        if self._sessions.get(chat_id, _Session(ChatState.IDLE)).state != ChatState.WAITING_VOICE:
            return
        await self._emit_round(chat_id)

    async def _emit_round(self, chat_id: int) -> None:
        try:
            vi_text = await self._claude.generate_prompt()
        except Exception as e:
            log.warning("generate_prompt failed (chat=%s): %s", chat_id, e)
            await self._sender.send_text(chat_id, "Claude busy, thử lại sau vài giây.")
            return
        if not vi_text:
            await self._sender.send_text(chat_id, "Claude trả về rỗng, thử lại.")
            return

        self._sessions[chat_id] = _Session(
            state=ChatState.WAITING_VOICE, last_vi_prompt=vi_text,
        )
        # Text first (fast read).
        await self._sender.send_text(chat_id, f"🇻🇳  {vi_text}")

        with self._make_work_dir() as work:
            try:
                ogg = self._audio.synthesize_vi(
                    vi_text, work, vi_voice=self._vi_voice, en_voice=self._en_voice,
                )
                await self._sender.send_voice(chat_id, ogg)
            except AudioError as e:
                log.warning("synthesize_vi failed (chat=%s): %s", chat_id, e)
                # Fallback: text-only. State still WAITING_VOICE.

    async def _deliver_feedback(self, chat_id: int, fb: Feedback) -> None:
        await self._sender.send_text(chat_id, fb.evaluation_text)
        with self._make_work_dir() as work:
            try:
                model_ogg = self._audio.synthesize_en(fb.model_english, work,
                                                     voice=self._en_voice, rate=140)
                await self._sender.send_voice(chat_id, model_ogg)
            except AudioError as e:
                log.warning("synthesize_en (model) failed (chat=%s): %s", chat_id, e)
            try:
                summary_text = fb.vi_summary
                if "Câu tiếp theo" not in summary_text:
                    summary_text = summary_text.rstrip(". ") + ". Câu tiếp theo."
                vi_ogg = self._audio.synthesize_vi(
                    summary_text, work,
                    vi_voice=self._vi_voice, en_voice=self._en_voice,
                )
                await self._sender.send_voice(chat_id, vi_ogg)
            except AudioError as e:
                log.warning("synthesize_vi (summary) failed (chat=%s): %s", chat_id, e)

    def _make_work_dir(self):
        if self._work_dir_factory is not None:
            class _Ctx:
                def __enter__(s): return Path(self._work_dir_factory())
                def __exit__(s, *a): return False
            return _Ctx()
        return tempfile.TemporaryDirectory(prefix="english_bot_")

```

> **Note:** `_make_work_dir` returns either a real `TemporaryDirectory` (production) or a test-provided directory (tests). In the test factory case it does NOT clean up — tests use `tmp_path` which pytest cleans automatically.

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_orchestrator.py -v
```
Expected: 5 passed. Adjust test assertions (e.g. `assert_awaited_with`) to match the real `Sender` interface if needed.

- [ ] **Step 5: Commit**

```bash
git add english_bot/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(bot): orchestrator state machine — begin/voice/stop round flow"
```

---

## Task 10: `poller.py` — Telegram handlers + whitelist

**Files:**
- Create: `english_bot/poller.py`
- Create: `tests/test_poller_whitelist.py`

- [ ] **Step 1: Write failing whitelist test**

`tests/test_poller_whitelist.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from english_bot.poller import is_allowed, build_application


def test_whitelist_accepts_allowed_ids():
    assert is_allowed(100, frozenset({100, 200})) is True


def test_whitelist_rejects_unknown_ids():
    assert is_allowed(999, frozenset({100, 200})) is False


def test_build_application_returns_object():
    # We don't actually network-connect — just verify the builder constructs
    # an Application with handlers registered.
    orch = MagicMock()
    app = build_application(
        token="xxx:dummy", orchestrator=orch, allowed_chat_ids=frozenset({1}),
    )
    # python-telegram-bot's Application exposes a `handlers` dict per group.
    handler_count = sum(len(hs) for hs in app.handlers.values())
    assert handler_count >= 3  # /start, /stop, voice
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_poller_whitelist.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `english_bot/poller.py`**

```python
"""Telegram long-polling Application + handler registration.

Whitelist enforced at the handler entry — non-allowed chat_ids are silently
ignored (no reply, only INFO log).
"""
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from english_bot.orchestrator import Orchestrator

log = logging.getLogger(__name__)


def is_allowed(chat_id: int, allowed: frozenset[int]) -> bool:
    return chat_id in allowed


class TelegramSender:
    """Adapter implementing the orchestrator's Sender Protocol."""

    def __init__(self, bot):
        self._bot = bot

    async def send_text(self, chat_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=chat_id, text=text)

    async def send_voice(self, chat_id: int, voice_path: Path) -> None:
        with open(voice_path, "rb") as f:
            await self._bot.send_voice(chat_id=chat_id, voice=f)


def build_application(
    token: str, orchestrator: Orchestrator, allowed_chat_ids: frozenset[int],
) -> Application:
    app = ApplicationBuilder().token(token).build()

    async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not is_allowed(chat_id, allowed_chat_ids):
            log.info("start: ignored non-allowed chat_id=%s", chat_id)
            return
        await orchestrator.begin_session(chat_id)

    async def stop_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not is_allowed(chat_id, allowed_chat_ids):
            log.info("stop: ignored non-allowed chat_id=%s", chat_id)
            return
        orchestrator.stop(chat_id)
        await app.bot.send_message(chat_id, "🛑 Stopped. /start để bắt đầu lại.")

    async def voice_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not is_allowed(chat_id, allowed_chat_ids):
            log.info("voice: ignored non-allowed chat_id=%s", chat_id)
            return
        voice = update.message.voice or update.message.audio
        if voice is None:
            return
        if voice.duration and voice.duration > 60:
            await app.bot.send_message(chat_id, "Voice quá dài (max 60s), thử lại.")
            return
        # Download to a temp file
        import tempfile
        tg_file = await voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            await tg_file.download_to_drive(custom_path=str(tmp_path))
            await orchestrator.handle_voice(chat_id, tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not is_allowed(chat_id, allowed_chat_ids):
            return
        # Only react if user sent text while in a session expecting voice.
        from english_bot.orchestrator import ChatState
        if orchestrator.state_of(chat_id) == ChatState.WAITING_VOICE:
            await app.bot.send_message(
                chat_id, "Đang chờ voice. Long-press 🎙 để ghi, hoặc /stop để dừng."
            )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Wire the sender now that the bot is available.
    orchestrator._sender = TelegramSender(app.bot)

    return app
```

> **Implementer note:** The last line (`orchestrator._sender = ...`) is a setter shortcut — feel free to refactor `Orchestrator` to take a sender via a setter method `set_sender()` for cleanliness if you prefer. The principle: `Orchestrator` is constructed before the `Application.bot` exists, so the sender is injected after.

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_poller_whitelist.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add english_bot/poller.py tests/test_poller_whitelist.py
git commit -m "feat(bot): telegram poller — handlers + whitelist + sender adapter"
```

---

## Task 11: `__main__.py` — entry point + signal handling

No unit tests for this thin entry point. Covered by the manual smoke test (Task 13).

**Files:**
- Create: `english_bot/__main__.py`

- [ ] **Step 1: Implement `english_bot/__main__.py`**

```python
"""Entry point: `python -m english_bot`."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from english_bot.audio import (  # noqa: F401 (module-level import for orchestrator)
    AudioError,
)
from english_bot import audio as audio_module
from english_bot.claude_client import ClaudeClient
from english_bot.config import Config, ConfigError
from english_bot.orchestrator import Orchestrator
from english_bot.poller import build_application


def main() -> int:
    load_dotenv()
    try:
        cfg = Config.from_env()
    except ConfigError as e:
        print(f"[FATAL] config error: {e}")
        return 1

    logging.basicConfig(
        level=cfg.log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("english_bot")
    log.info("starting, whitelist=%s", sorted(cfg.allowed_chat_ids))

    _check_required_binaries()

    system_prompt_path = Path(__file__).parent / "prompts" / "system.md"
    claude = ClaudeClient(system_prompt_path=system_prompt_path)

    orch = Orchestrator(
        claude=claude,
        audio=audio_module,
        sender=None,  # injected by build_application
        whisper_model=cfg.whisper_model,
        vi_voice=cfg.speak_voice,
        en_voice=cfg.speak_en_voice,
    )

    app = build_application(
        token=cfg.telegram_token,
        orchestrator=orch,
        allowed_chat_ids=cfg.allowed_chat_ids,
    )

    log.info("polling Telegram...")
    app.run_polling(stop_signals=None)  # python-telegram-bot handles SIGINT/SIGTERM internally
    log.info("shutdown clean")
    return 0


def _check_required_binaries() -> None:
    import shutil
    missing = [b for b in ("say", "ffmpeg", "whisper-cli") if shutil.which(b) is None]
    if missing:
        hint = "brew install whisper-cpp ffmpeg  # `say` ships with macOS"
        raise SystemExit(
            f"[FATAL] missing required binaries: {missing}. Install with: {hint}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke run (fails fast — no token configured)**

```bash
.venv/bin/python -m english_bot
```
Expected: `[FATAL] config error: TELEGRAM_BOT_TOKEN is required` and exit 1. **This is the desired result** — proves the fail-fast path works without needing a real token.

- [ ] **Step 3: Commit**

```bash
git add english_bot/__main__.py
git commit -m "feat(bot): __main__ — entry point + fail-fast binary check"
```

---

## Task 12: `scripts/run_bot.sh` + README + smoke checklist

**Files:**
- Create: `scripts/run_bot.sh`
- Create: `tests/smoke.md`
- Modify: `README.md`

- [ ] **Step 1: Write `scripts/run_bot.sh`**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/run_bot.sh
```

- [ ] **Step 3: Write `tests/smoke.md`**

```markdown
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
```

- [ ] **Step 4: Update `README.md`**

Append a new section after the existing content (before `## License`). The
fenced ```` ```markdown ```` block below is for display only — when copying
into `README.md`, strip the outer fence and paste only the content inside:

```markdown
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

### Run

```bash
./scripts/run_bot.sh   # Ctrl-C to stop
```

On iPhone: open Telegram → your bot → `/start` → long-press 🎙 to reply →
`/stop` when done.

Bot only runs while this macOS terminal is open and the laptop is awake.
Whitelist enforced: chats outside `ALLOWED_CHAT_IDS` are silently ignored.

See [tests/smoke.md](tests/smoke.md) for the full manual checklist.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/run_bot.sh tests/smoke.md README.md
git commit -m "feat(bot): launcher script + README section + manual smoke checklist"
```

---

## Task 13: Full test suite + manual smoke

- [ ] **Step 1: Run full unit + integration suite**

```bash
.venv/bin/pytest -v
```
Expected: all tests PASS (audio integration tests need macOS + `WHISPER_MODEL` env). Skips OK on non-macOS.

- [ ] **Step 2: Run manual smoke**

Follow `tests/smoke.md` end-to-end on iPhone Telegram. Tick each box as you go.

- [ ] **Step 3: Final commit (any smoke-test fixes)**

If anything broke during smoke and you fixed it (typo in prompt, voice timing, etc.), commit those fixes with a clear message. Otherwise skip this step.

```bash
git status
git add ...
git commit -m "fix(bot): smoke-test polish — <what>"
```

---

## Implementation notes (read before starting Task 8)

1. **Claude Agent SDK shape**: The SDK API has evolved. Before writing `claude_client.py`, run:
   ```bash
   .venv/bin/python -c "
   import claude_agent_sdk
   print(dir(claude_agent_sdk))
   print(claude_agent_sdk.__version__)
   "
   ```
   to confirm `ClaudeSDKClient`, `ClaudeAgentOptions`, and `receive_response()` exist. If the API differs, adjust `_query()` only — the rest of the bot depends on `string → string`.

2. **Authentication via Claude MAX subscription**: The Claude Agent SDK reads `~/.claude/` credentials automatically when no explicit API key is provided. Confirm by running `claude --version` once first to ensure you're logged in. Do NOT set `ANTHROPIC_API_KEY` in `.env` — that switches to paid API billing.

3. **`python-telegram-bot` async**: Version 21.x is fully async. All handlers must be `async def`. `app.run_polling()` blocks and handles SIGINT/SIGTERM gracefully.

4. **Markdown escaping**: Telegram's MarkdownV2 mode requires escaping `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`. For v1, send plain text (no `parse_mode`). The feedback emoji + bullets render fine as plain. If you want bold/code formatting later, use `parse_mode="MarkdownV2"` and escape carefully — but YAGNI for v1.

5. **Per-round temp dir**: `tempfile.TemporaryDirectory()` in `_emit_round` and `_deliver_feedback` cleans up even on exception. Don't leak files.

6. **Don't re-use existing scripts**: `scripts/speak.sh` and `scripts/record.sh` are for the terminal version. They use the speakers / mic — incompatible with the bot's file-based flow. The bot calls `say`, `ffmpeg`, `whisper-cli` directly via `subprocess`.

7. **Single existing user**: For initial run, set `ALLOWED_CHAT_IDS` to just your own chat_id. Add others later via `.env` (no code change needed).

8. **DO NOT**: Add features beyond this plan (streaks, history, multi-language, inline keyboards, webhook mode, Docker). They are explicitly out of scope (spec §Out of Scope).
