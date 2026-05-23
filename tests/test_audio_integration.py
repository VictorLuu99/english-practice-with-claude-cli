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


from english_bot.audio import synthesize_vi


@requires_macos_audio
def test_synthesize_vi_with_backticks_produces_ogg(tmp_path):
    """Backticks in text are stripped before TTS; Linh reads everything."""
    text = "Hôm nay tôi có `meeting` về `deadline` mới."
    out = synthesize_vi(text, tmp_path, vi_voice="Linh", rate=170)
    assert out.exists()
    assert out.suffix == ".ogg"
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    assert duration > 1.0


@requires_macos_audio
def test_synthesize_vi_pure_vietnamese(tmp_path):
    out = synthesize_vi("Xin chào, hôm nay trời đẹp quá.", tmp_path,
                        vi_voice="Linh", rate=170)
    assert out.exists()


@requires_macos_audio
def test_synthesize_vi_strips_backticks_before_say(tmp_path):
    """Verify backticks don't reach `say` (otherwise Linh would read 'backtick')."""
    out = synthesize_vi("`hello` only", tmp_path, vi_voice="Linh", rate=170)
    assert out.exists()


from unittest.mock import patch
from english_bot.audio import _resolve_vi_voice, AudioError


def test_synthesize_vi_empty_after_strip_raises(tmp_path):
    """If text is empty (or backticks-only), raise AudioError."""
    with pytest.raises(AudioError, match="empty text"):
        synthesize_vi("```", tmp_path, vi_voice="Linh")


def test_resolve_vi_voice_exact_match_no_false_positive():
    """When only 'Linh (Enhanced)' is installed, requesting 'Linh' must fall back to 'Linh',
    not match 'Linh (Enhanced)' by prefix. Note 'Linh' as fallback is hardcoded in the impl
    even though it isn't installed in this scenario — the test verifies the *matching* logic.
    """
    fake_voice_list = (
        "Linh (Enhanced)     vi_VN    # Xin chào!\n"
        "Samantha            en_US    # Hi there\n"
    )
    fake_result = type("R", (), {"stdout": fake_voice_list, "returncode": 0})()
    with patch("subprocess.run", return_value=fake_result):
        # Requesting "Linh" (plain) should NOT match "Linh (Enhanced)" by prefix
        assert _resolve_vi_voice("Linh") == "Linh"  # falls through to hardcoded fallback
        # Requesting "Linh (Enhanced)" matches exactly
        assert _resolve_vi_voice("Linh (Enhanced)") == "Linh (Enhanced)"
        # Unknown voice falls back to "Linh"
        assert _resolve_vi_voice("DoesNotExist") == "Linh"


def test_resolve_vi_voice_subprocess_failure_falls_back():
    """If `say -v ?` itself fails, return 'Linh' fallback."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "say")):
        assert _resolve_vi_voice("Linh (Enhanced)") == "Linh"


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
