"""Telegram long-polling Application + handler registration.

Whitelist enforced at the handler entry — non-allowed chat_ids are silently
ignored (no reply, only INFO log).
"""
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from english_bot.orchestrator import ChatState, Orchestrator

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
    token: str,
    orchestrator: Orchestrator,
    allowed_chat_ids: frozenset[int],
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
            log.info("text: ignored non-allowed chat_id=%s", chat_id)
            return
        # Only react if user sent text while in a session expecting voice.
        if orchestrator.state_of(chat_id) == ChatState.WAITING_VOICE:
            await app.bot.send_message(
                chat_id,
                "Đang chờ voice. Long-press 🎙 để ghi, hoặc /stop để dừng.",
            )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Wire the sender now that the bot object is available.
    # Using set_sender() (option a) for a clean public contract rather than
    # direct private attribute mutation.
    orchestrator.set_sender(TelegramSender(app.bot))

    return app
