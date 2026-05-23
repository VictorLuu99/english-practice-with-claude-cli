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
