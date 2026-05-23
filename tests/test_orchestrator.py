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
    # Sender should receive a text hint mentioning /start
    fake_sender.send_text.assert_awaited()
    # Extract the text argument from the first call and assert it mentions "start"
    call_args = fake_sender.send_text.await_args
    # call_args.args is (chat_id, text) or call_args.kwargs has text= depending on style
    text_sent = call_args.args[-1] if call_args.args else call_args.kwargs.get("text", "")
    assert "start" in text_sent.lower()


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


async def test_emit_round_failure_cleans_up_session(fake_audio, fake_sender, tmp_path):
    """If generate_prompt fails, the session is removed so next voice gets the IDLE hint."""
    claude = MagicMock()
    claude.generate_prompt = AsyncMock(side_effect=RuntimeError("Claude down"))
    orch = Orchestrator(
        claude=claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    # Session should be removed; state_of returns IDLE for missing chats
    assert orch.state_of(42) == ChatState.IDLE
    # Next voice should get the "Gõ /start" hint, NOT trigger transcribe
    fake_sender.send_text.reset_mock()
    await orch.handle_voice(chat_id=42, voice_path=tmp_path / "v.ogg")
    fake_audio.transcribe.assert_not_called()


async def test_tts_failure_notifies_user(fake_claude, fake_sender, tmp_path):
    """Spec line 189: TTS failure must send 'Lỗi TTS, skip voice.' to the user."""
    from english_bot.audio import AudioError
    fake_audio = MagicMock()
    fake_audio.synthesize_vi = MagicMock(side_effect=AudioError("say crashed"))
    orch = Orchestrator(
        claude=fake_claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    # Vi text should have been sent (text-first), then TTS attempt fails
    # and we expect a 'Lỗi TTS' message to follow.
    sent_texts = [
        call.args[-1] if call.args else call.kwargs.get("text", "")
        for call in fake_sender.send_text.await_args_list
    ]
    assert any("Lỗi TTS" in t for t in sent_texts), f"got: {sent_texts}"


async def test_transcribe_called_via_to_thread(fake_claude, fake_audio, fake_sender, tmp_path, monkeypatch):
    """Subprocess audio calls must go through asyncio.to_thread so the event
    loop isn't blocked. Verify by patching to_thread and checking it was called."""
    import asyncio
    real_to_thread = asyncio.to_thread
    spy = AsyncMock(side_effect=lambda fn, *a, **kw: real_to_thread(fn, *a, **kw))
    monkeypatch.setattr(asyncio, "to_thread", spy)

    orch = Orchestrator(
        claude=fake_claude, audio=fake_audio, sender=fake_sender,
        whisper_model="/tmp/m", vi_voice="Linh", en_voice="Samantha",
        work_dir_factory=lambda: tmp_path,
    )
    await orch.begin_session(chat_id=42)
    await orch.handle_voice(chat_id=42, voice_path=tmp_path / "v.ogg")
    # to_thread should have been called for transcribe (at minimum)
    assert spy.await_count >= 1
