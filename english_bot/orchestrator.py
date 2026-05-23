"""Per-chat state machine driving the Vi prompt → Eng answer → feedback loop."""
import asyncio
import logging
import shutil
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


class _FactoryContext:
    """Context manager wrapping a work_dir_factory callable."""

    def __init__(self, factory: Callable[[], Path]) -> None:
        self._factory = factory

    def __enter__(self) -> Path:
        return Path(self._factory())

    def __exit__(self, *args) -> bool:
        return False


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

    def set_sender(self, sender: "Sender") -> None:
        """Inject (or replace) the Sender adapter after construction.

        Useful when the Telegram bot object is only available after
        ApplicationBuilder().build() completes.
        """
        self._sender = sender

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
            with tempfile.TemporaryDirectory(prefix="english_bot_tr_") as tr_work:
                tr_voice = Path(tr_work) / "user.ogg"
                shutil.copy2(voice_path, tr_voice)
                transcript = await asyncio.to_thread(
                    self._audio.transcribe, tr_voice, model_path=self._whisper_model
                )
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
            await self._sender.send_text(
                chat_id, "Claude busy. Gõ /start lại để thử lần nữa."
            )
            self._sessions.pop(chat_id, None)
            return
        if not vi_text:
            await self._sender.send_text(
                chat_id, "Claude trả về rỗng. Gõ /start lại để thử lần nữa."
            )
            self._sessions.pop(chat_id, None)
            return

        self._sessions[chat_id] = _Session(
            state=ChatState.WAITING_VOICE, last_vi_prompt=vi_text,
        )
        # Text first (fast read).
        await self._sender.send_text(chat_id, f"🇻🇳  {vi_text}")

        with self._make_work_dir() as work:
            work = Path(work)  # normalise — TemporaryDirectory returns str, _FactoryContext returns Path
            try:
                ogg = await asyncio.to_thread(
                    self._audio.synthesize_vi,
                    vi_text, work, vi_voice=self._vi_voice, en_voice=self._en_voice,
                )
                await self._sender.send_voice(chat_id, ogg)
            except AudioError as e:
                log.warning("synthesize_vi failed (chat=%s): %s", chat_id, e)
                await self._sender.send_text(chat_id, "Lỗi TTS, skip voice.")
                # Fallback: text-only. State still WAITING_VOICE.

    async def _deliver_feedback(self, chat_id: int, fb: Feedback) -> None:
        await self._sender.send_text(chat_id, fb.evaluation_text)
        with self._make_work_dir() as work:
            work = Path(work)  # normalise
            try:
                model_ogg = await asyncio.to_thread(
                    self._audio.synthesize_en,
                    fb.model_english, work, voice=self._en_voice, rate=140,
                )
                await self._sender.send_voice(chat_id, model_ogg)
            except AudioError as e:
                log.warning("synthesize_en (model) failed (chat=%s): %s", chat_id, e)
                await self._sender.send_text(chat_id, "Lỗi TTS, skip voice.")
            try:
                summary_text = fb.vi_summary
                if "Câu tiếp theo" not in summary_text:
                    summary_text = summary_text.rstrip(". ") + ". Câu tiếp theo."
                vi_ogg = await asyncio.to_thread(
                    self._audio.synthesize_vi,
                    summary_text, work,
                    vi_voice=self._vi_voice, en_voice=self._en_voice,
                )
                await self._sender.send_voice(chat_id, vi_ogg)
            except AudioError as e:
                log.warning("synthesize_vi (summary) failed (chat=%s): %s", chat_id, e)
                await self._sender.send_text(chat_id, "Lỗi TTS, skip voice.")

    def _make_work_dir(self):
        if self._work_dir_factory is not None:
            return _FactoryContext(self._work_dir_factory)
        return tempfile.TemporaryDirectory(prefix="english_bot_")
