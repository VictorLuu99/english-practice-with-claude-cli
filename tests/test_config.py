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
