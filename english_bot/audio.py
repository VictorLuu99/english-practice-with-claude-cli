"""Subprocess wrappers for macOS audio I/O.

Pipeline:
  - synthesize_en/vi: `say -o aiff` → `ffmpeg → ogg/opus` (Telegram-friendly)
  - transcribe: incoming ogg → `ffmpeg → 16kHz mono wav` → `whisper-cli` → text

No live mic capture (Telegram delivers pre-recorded voice notes), so sox/rec
is NOT used here. The terminal scripts `speak.sh` and `record.sh` stay
untouched for the slash-command flow.
"""
import subprocess
from pathlib import Path


class AudioError(RuntimeError):
    """Raised when an audio subprocess fails."""


def synthesize_en(text: str, work_dir: Path, voice: str = "Samantha",
                  rate: int = 140) -> Path:
    """Render plain English to an Opus-in-OGG file using macOS `say` + ffmpeg.

    Args:
        text: English text to synthesize (no backtick splitting).
        work_dir: existing directory for intermediate + output files.
            Caller owns cleanup; the intermediate .aiff is intentionally
            left in work_dir (don't add unlink() here — synthesize_vi in
            Task 6 keeps per-chunk .aiff files in the same dir for concat).
        voice: macOS voice name (default Samantha).
        rate: words per minute (default 140 — slow for listening practice).

    Returns:
        Path to the .ogg file inside work_dir.
    """
    aiff_path = work_dir / "en.aiff"
    ogg_path = work_dir / "en.ogg"
    _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff_path), text])
    _aiff_to_ogg(aiff_path, ogg_path)
    return ogg_path


def _aiff_to_ogg(aiff_path: Path, ogg_path: Path) -> None:
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(aiff_path),
        "-c:a", "libopus", "-b:a", "48k",
        str(ogg_path),
    ])


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise AudioError(
            f"{cmd[0]} failed (exit {result.returncode}): {detail}"
        )
