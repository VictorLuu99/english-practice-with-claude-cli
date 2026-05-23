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
