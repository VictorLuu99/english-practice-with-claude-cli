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


from english_bot.audio import synthesize_vi, _split_backticks


def test_split_backticks_alternates():
    parts = _split_backticks("Hôm nay tôi có `meeting` về `deadline` mới.")
    # Returns list[(is_english, text)]
    assert parts == [
        (False, "Hôm nay tôi có"),
        (True, "meeting"),
        (False, "về"),
        (True, "deadline"),
        (False, "mới."),
    ]


def test_split_backticks_no_english():
    parts = _split_backticks("Câu thuần Việt không có backticks.")
    assert parts == [(False, "Câu thuần Việt không có backticks.")]


def test_split_backticks_strips_whitespace_only_chunks():
    parts = _split_backticks("`hello`")
    assert parts == [(True, "hello")]


@requires_macos_audio
def test_synthesize_vi_bilingual_produces_ogg(tmp_path):
    text = "Hôm nay tôi có `meeting` về `deadline` mới."
    out = synthesize_vi(text, tmp_path, vi_voice="Linh", en_voice="Samantha", rate=170)
    assert out.exists()
    assert out.suffix == ".ogg"
    # Concat result should be > sum of individual chunk minimum durations
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    assert duration > 1.0  # multi-chunk Vi+En sentence


@requires_macos_audio
def test_synthesize_vi_pure_vietnamese_no_concat(tmp_path):
    out = synthesize_vi("Xin chào, hôm nay trời đẹp quá.", tmp_path,
                        vi_voice="Linh", en_voice="Samantha", rate=170)
    assert out.exists()


from unittest.mock import patch
from english_bot.audio import _resolve_vi_voice, AudioError


def test_split_backticks_raises_on_odd_count():
    with pytest.raises(AudioError, match="unmatched backtick"):
        _split_backticks("Vi text ` more Vi")


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
