# Telegram bot for English speaking practice — Design

**Date:** 2026-05-23
**Status:** Draft (pending review)
**Author:** brainstormed with Claude

## Motivation

The current English practice tool runs as a Claude Code slash command on the
macOS terminal. It cannot be used away from the laptop. The user wants to
practice on the iPhone (e.g. lying down, on the move) using the same loop
(Vi prompt → spoken English → corrective feedback) without leaving the existing
free-under-MAX architecture.

The terminal version stays. The new Telegram bot is a parallel client surface
that runs on the same macOS host and reuses the same audio pipeline.

## Goals

- iPhone can drive a full practice round through the Telegram app.
- Same loop semantics as the terminal version: stateless rounds, random topics,
  Vi prompt with English loanwords in backticks, bilingual TTS, English STT,
  Vi-language feedback summary referencing the model English phrase.
- $0 marginal cost: orchestration via Claude Agent SDK with the user's Claude
  MAX subscription (no API billing); STT via local `whisper-cli`; TTS via
  macOS `say`.
- Multi-user (whitelist), single host (one macOS), single process.

## Non-Goals (YAGNI)

- No website / cloudflared tunnel (other option ruled out).
- No persistent state, streak tracking, or weak-spot learning.
- No inline keyboards or custom Telegram UI affordances.
- No Docker, no cloud deploy.
- No multi-language UI (only Vi prompt + En answer).
- No replacement for the terminal slash command; both coexist.

## Architecture

Single Python process on macOS. Three logical layers inside one process:

```
┌──────────────────────────────────────────────────────────┐
│ macOS bot process (python -m english_bot)                │
│                                                           │
│  ┌────────────────┐    ┌──────────────────┐              │
│  │ Telegram poller│◄──►│ Round orchestrator│             │
│  │ (long-polling) │    │ (per chat_id state│             │
│  └────────────────┘    │  machine: idle/   │             │
│         ▲              │   waiting_voice)  │             │
│         │              └──────────────────┘              │
│         │                       │                         │
│         │                       ▼                         │
│         │              ┌──────────────────┐              │
│         │              │ Claude Agent SDK │              │
│         │              │  (subscription)  │              │
│         │              └──────────────────┘              │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────────────────────────────┐                │
│  │ Audio I/O (subprocess wrappers)      │                │
│  │  - say  -o file.aiff  (Vi/En TTS)    │                │
│  │  - ffmpeg  (aiff↔ogg/opus)           │                │
│  │  - whisper-cli  (En STT từ file)     │                │
│  └──────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────┘
       ▲                                          │
       │ HTTPS long-poll                         │
       ▼                                          ▼
  Telegram Bot API ◄──────────────► iPhone (Telegram app)
```

### Key architectural choices

- **Long-polling Telegram updates.** No webhook, no public URL, no tunnel.
  `python-telegram-bot` handles polling, retries, backoff internally.
- **Per-chat state machine in RAM.** Dict `{chat_id → state}` where state ∈
  `{IDLE, WAITING_VOICE, STOPPED}`. No DB.
- **Whitelist enforced at the poller boundary.** Any update from a non-allowed
  `chat_id` is silently dropped before handlers run.
- **Per-round Claude SDK call (stateless).** Each round creates a fresh
  `ClaudeSDKClient` query: one query to generate the Vi prompt, one query to
  evaluate the transcript. No session persistence between rounds.
- **Audio temp files** live in `tempfile.TemporaryDirectory()` per round and
  are auto-removed when the round exits.

## Components

Package `english_bot/`:

| Module | Responsibility | Depends on |
|---|---|---|
| `__main__.py` | Entry point. Load config, start poller loop. Handle SIGINT/SIGTERM graceful shutdown. | `config`, `poller` |
| `config.py` | Load env vars (`TELEGRAM_BOT_TOKEN`, `ALLOWED_CHAT_IDS`, `WHISPER_MODEL`, `SPEAK_VOICE`, `SPEAK_EN_VOICE`, `LOG_LEVEL`). Fail-fast if missing. | stdlib |
| `poller.py` | `python-telegram-bot` Application with long-polling. Registers `/start`, `/stop`, voice MessageHandler. Whitelist check per update. | `telegram`, `orchestrator` |
| `orchestrator.py` | Per-chat state machine. Drives `/start` → emit round → wait → on voice reply: evaluate + emit next round. `/stop` halts loop. | `claude_client`, `audio` |
| `claude_client.py` | Wrapper around `claude-agent-sdk`. Two functions: `generate_prompt() -> str` returns a Vi sentence; `evaluate(prompt, transcript) -> Feedback`. Each invocation = one fresh stateless query. | `claude_agent_sdk` |
| `audio.py` | Subprocess wrappers. `synthesize_vi(text) -> ogg_path` (Vi/En bilingual split on backticks, same convention as `speak.sh`); `synthesize_en(text) -> ogg_path` (Samantha rate 140); `transcribe(ogg_path) -> str`. | `subprocess`, `ffmpeg`, `say`, `whisper-cli` |
| `models.py` | `Feedback` dataclass: `transcript`, `evaluation_text`, `model_english`, `vi_summary`. Claude returns JSON matching this shape (structured output). | `dataclasses` |
| `prompts/system.md` | System prompt for Claude. Ported from `.claude/skills/english-practice.md`, with Bash tool invocations stripped (this is non-interactive). Defines: free-form topic generation, Vi prompt format with backticks for English loanwords, JSON feedback schema. | — |

Outside package: `scripts/run_bot.sh` — venv activate + `python -m english_bot`.

## Data flow — one round

```
[User on iPhone: /start]
  │
  ▼
poller.start_handler(chat_id)
  - whitelist check
  - orchestrator.begin_session(chat_id)   # state[chat_id] = WAITING_VOICE
  │
  ▼
orchestrator._emit_round(chat_id):
  ┌─ claude_client.generate_prompt()
  │    → ClaudeSDKClient query: "Sinh 1 câu Vi (random topic, English wrap `backticks`)"
  │    → "Hôm nay tôi có `meeting` về `deadline` mới."
  │
  ├─ bot.send_message(chat_id, vi_text)            # text first (fast read)
  │
  ├─ audio.synthesize_vi(vi_text) → /tmp/.../vi.ogg
  │    (backtick split: Vi chunks → Linh, En chunks → Samantha;
  │     ffmpeg concat → 1 ogg/opus file)
  │
  └─ bot.send_voice(chat_id, vi.ogg)               # user hears Vi prompt
  │
  ▼
[User long-press mic, speaks English, sends voice]
  │
  ▼
poller.voice_handler(update):
  - state == WAITING_VOICE? → proceed
  - bot.download(voice.file_id) → /tmp/.../user.ogg
  │
  ▼
orchestrator._handle_reply(chat_id, user_ogg):
  ┌─ audio.transcribe(user_ogg)
  │    → ffmpeg user.ogg → user.wav (16kHz mono)
  │    → whisper-cli ggml-small.en.bin → transcript str
  │
  ├─ claude_client.evaluate(vi_prompt, transcript)
  │    → ClaudeSDKClient query with feedback system prompt
  │    → Feedback(transcript, evaluation_text, model_english, vi_summary)
  │
  ├─ bot.send_message(chat_id, format_feedback_markdown(feedback))
  │    (Markdown V2: transcript, ✅/❌, model_english bold, breakdown)
  │
  ├─ audio.synthesize_en(model_english) → /tmp/.../model.ogg  (Samantha rate 140)
  ├─ bot.send_voice(chat_id, model.ogg)
  │
  ├─ audio.synthesize_vi(vi_summary + " Câu tiếp theo.") → /tmp/.../summary.ogg
  └─ bot.send_voice(chat_id, summary.ogg)
  │
  ▼
orchestrator._emit_round(chat_id)   # loop into next round
                                    # (unless state has been set to STOPPED by /stop meanwhile)
```

### Concurrency model

Each `chat_id` runs rounds sequentially via `await`-based async I/O. Multiple
`chat_id`s execute concurrently because `python-telegram-bot` dispatches
handlers on the asyncio event loop. Stateless per-round means no shared
locking beyond the per-chat state dict (single-threaded asyncio access is
safe).

### Cancellation

`/stop` sets `state[chat_id] = STOPPED`. The in-flight round checks the flag
after each async step (TTS send, await voice, transcribe, evaluate) and
returns early when set. The next round is not emitted.

## Error handling

Principle: **never crash the bot**, a failing round informs the user and the
state machine keeps moving. Crash only on startup config errors (fail-fast).

| Failure | Where | Behavior |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` missing/invalid | startup | Raise, exit with clear log. |
| `ALLOWED_CHAT_IDS` empty | startup | Raise, exit (avoid accidentally-public bot). |
| `whisper-cli` / `say` / `ffmpeg` missing | startup | Raise, exit with install hint (`brew install ...`). |
| Telegram API timeout / network blip | poller loop | `python-telegram-bot` auto-retries with backoff. Log warning. |
| Voice file > 60s | voice_handler | Reply "Voice quá dài (max 60s), thử lại." No state advance. |
| Whisper transcribes empty string | audio.transcribe | Reply "Không nghe rõ, thử lại." State stays `WAITING_VOICE`. |
| Claude SDK timeout / network blip | claude_client | Reply "Claude busy, thử lại sau vài giây." State stays `WAITING_VOICE`. |
| Claude returns malformed JSON | claude_client.evaluate | Parse fail → reply raw text + warning. Round advances anyway (no stuck). |
| `say` / `ffmpeg` subprocess non-zero exit | audio | Log stderr. Reply "Lỗi TTS, skip voice." Fall back to text-only, advance. |
| User sends text while `WAITING_VOICE` | voice_handler | Reply: "Đang chờ voice. Long-press 🎙 để ghi, hoặc /stop để dừng." |
| User sends voice while `IDLE` | voice_handler | Reply: "Gõ /start để bắt đầu." |
| `/start` while `WAITING_VOICE` | start_handler | Reply: "Session đang chạy. /stop trước." Ignore. |
| Update from non-whitelist chat_id | poller (all handlers) | Silent drop (don't leak bot identity). Log info. |
| SIGINT / SIGTERM | __main__ | Stop poller, cancel pending tasks, cleanup temp dirs, exit 0. |

**Logging.** stdlib `logging`, INFO by default, DEBUG via `LOG_LEVEL=DEBUG`.
Format: `[time] [level] [chat_id=X] message`. Output to stderr.

**Temp file cleanup.** Each round uses `tempfile.TemporaryDirectory()`,
auto-cleaned on context exit even when the round errors out.

## Testing strategy

Thin pyramid — personal tool, not chasing coverage. Focus: unit tests for
logic with branches, integration tests for the subprocess audio pipeline,
manual smoke for end-to-end Telegram round-trip.

### Unit (pytest, mock heavy)

| File | Focus |
|---|---|
| `tests/test_config.py` | Missing env → raise. `ALLOWED_CHAT_IDS="1,2,3"` parses to `{1,2,3}`. Invalid chat_id type → raise. |
| `tests/test_orchestrator.py` | `/start` from `IDLE` → `WAITING_VOICE` and emits round. `/stop` from `WAITING_VOICE` → `STOPPED` and no further emit. Voice reply while `WAITING_VOICE` → evaluate + emit next round. Voice while `IDLE` → hint reply. Mocks `claude_client`, `audio`, bot send methods. |
| `tests/test_claude_client.py` | `generate_prompt()` returns non-empty str. `evaluate()` parses JSON → `Feedback`. Malformed JSON raises typed exception. Mocks `ClaudeSDKClient`. |
| `tests/test_poller_whitelist.py` | Update from non-allowed chat_id → handlers silent-ignored. Constructs `Update` fixture. |

### Integration (real subprocesses, no Telegram, no Claude)

| File | Focus |
|---|---|
| `tests/test_audio_integration.py` | `pytest.skip` if `say` / `ffmpeg` / `whisper-cli` not on PATH. `synthesize_vi("Xin chào `world`")` → ogg file exists, duration > 0. `transcribe(fixture_wav)` → non-empty string. Verify bilingual branch: input with backticks invokes the En voice path (via `audio` exposing the split for assertion). |

### Manual smoke

A `tests/smoke.md` checklist (not automated):

1. Set env vars, run `./scripts/run_bot.sh`.
2. On iPhone Telegram: `/start` → receive Vi text + voice within ~5s.
3. Long-press mic, speak one English sentence → receive feedback text + Samantha
   voice (model English) + Linh voice summary + next round automatically.
4. `/stop` → bot stops emitting; sending anything does not resume the loop.
5. From a non-whitelist Telegram account, send `/start` → no reply.
6. Drop network mid-round → "Claude busy" reply → reconnect → `/start` works.

### Not tested

- `python-telegram-bot` framework internals (well-maintained upstream).
- Claude model output quality (mocked in unit tests; covered by smoke).
- macOS `say` voice quality (subjective; covered by smoke).

## File layout

```
enghlish_q_n_a/
├── .claude/skills/english-practice.md        # unchanged (terminal version)
├── scripts/
│   ├── setup.sh                              # unchanged
│   ├── speak.sh                              # unchanged
│   ├── record.sh                             # unchanged
│   └── run_bot.sh                            # NEW — venv activate + python -m english_bot
├── english_bot/                              # NEW package
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── poller.py
│   ├── orchestrator.py
│   ├── claude_client.py
│   ├── audio.py
│   ├── models.py
│   └── prompts/
│       └── system.md                         # ported from skill, Bash bits stripped
├── tests/                                    # NEW
│   ├── conftest.py
│   ├── fixtures/
│   │   └── sample_voice.wav                  # short, used by transcribe test
│   ├── test_config.py
│   ├── test_orchestrator.py
│   ├── test_claude_client.py
│   ├── test_poller_whitelist.py
│   ├── test_audio_integration.py
│   └── smoke.md
├── pyproject.toml                            # NEW — deps + tool config
├── .env.example                              # NEW — env vars
├── .gitignore                                # updated — .venv/, .env, __pycache__/
├── docs/superpowers/specs/
│   └── 2026-05-23-telegram-bot-design.md     # this doc
└── README.md                                 # updated — Telegram bot section
```

## Dependencies (`pyproject.toml`)

| Package | Reason | Version |
|---|---|---|
| `python-telegram-bot[ext]` | Telegram long-polling + handlers | `^21.0` |
| `claude-agent-sdk` | Claude orchestration w/ subscription auth | latest |
| `python-dotenv` | `.env` loading at dev time | `^1.0` |
| `pytest` + `pytest-asyncio` | Test runner (dev dep) | latest |

Python 3.11+ required (`tomllib` stdlib, asyncio maturity, modern type hints).

## Env vars (`.env.example`)

```
TELEGRAM_BOT_TOKEN=
ALLOWED_CHAT_IDS=123456789,987654321
WHISPER_MODEL=/Users/vuongluu/.cache/whisper-cpp/ggml-small.en.bin
SPEAK_VOICE=Linh (Enhanced)
SPEAK_EN_VOICE=Samantha
LOG_LEVEL=INFO
```

## One-time setup

1. Create bot via `@BotFather` on Telegram → copy `TELEGRAM_BOT_TOKEN`.
2. Send any message to the bot from your iPhone, then read your `chat_id` via
   `getUpdates`.
3. Copy `.env.example` → `.env`, fill in token + chat_ids.
4. `python -m venv .venv && .venv/bin/pip install -e .`
5. `./scripts/run_bot.sh` to start.

## Out of scope

- Website / cloudflared tunnel (other branch of the original choice; ruled out).
- Persistent state, streak tracking, long-term memory.
- Telegram inline keyboards, custom buttons, formatted menus.
- Docker, cloud hosting, CI deploy.
- Multi-language UI.
- Password auth (whitelist is the only access control).
- Replacing the terminal slash command (it stays usable in parallel).
