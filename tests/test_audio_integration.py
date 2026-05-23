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
