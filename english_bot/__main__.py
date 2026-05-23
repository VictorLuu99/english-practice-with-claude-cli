"""Entry point: `python -m english_bot`."""
import logging
from pathlib import Path

from dotenv import load_dotenv

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
