from unittest.mock import AsyncMock, MagicMock

import pytest

from english_bot.poller import is_allowed, build_application, reply_chat_id_hint


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


async def test_reply_chat_id_hint_sends_html_formatted_message():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    await reply_chat_id_hint(bot, 1727536993)
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 1727536993
    assert kwargs["parse_mode"] == "HTML"
    assert "1727536993" in kwargs["text"]
    assert "<code>1727536993</code>" in kwargs["text"]
    assert "whitelist" in kwargs["text"].lower()
