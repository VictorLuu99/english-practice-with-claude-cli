"""Subprocess wrappers for macOS audio I/O.

Pipeline:
  - synthesize_en/vi: `say -o aiff` → `ffmpeg → ogg/opus` (Telegram-friendly)
  - transcribe: incoming ogg → `ffmpeg → 16kHz mono wav` → `whisper-cli` → text

No live mic capture (Telegram delivers pre-recorded voice notes), so sox/rec
is NOT used here. The terminal scripts `speak.sh` and `record.sh` stay
untouched for the slash-command flow.
"""
import re
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


def synthesize_vi(text: str, work_dir: Path, vi_voice: str = "Linh (Enhanced)",
                  rate: int = 170) -> Path:
    """Render Vi text to an Opus-in-OGG file using Linh (single-voice).

    Backticks in the input are stripped before TTS — they're a display
    convention from Claude (visually mark English in Telegram text), but
    `say` would otherwise read them literally. Linh handles English words
    with a Vietnamese accent; that's intentional (user prefers a single
    cohesive voice). Use synthesize_en separately when you need accurate
    English pronunciation for the model phrase.

    Args:
        text: Vi text, may contain backticks around English fragments
            (which get stripped before TTS).
        work_dir: existing dir for intermediate + output files (caller-owned).
        vi_voice: macOS voice name (falls back to plain "Linh" if Enhanced
            isn't installed).
        rate: words per minute.

    Returns:
        Path to the .ogg file inside work_dir.
    """
    clean_text = text.replace("`", "").strip()
    if not clean_text:
        raise AudioError("synthesize_vi got empty text")
    voice = _resolve_vi_voice(vi_voice)
    aiff = work_dir / "vi.aiff"
    ogg = work_dir / "vi.ogg"
    _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), clean_text])
    _aiff_to_ogg(aiff, ogg)
    return ogg


_VOICE_LINE_LOCALE_RE = re.compile(r"\s+[a-z]+_[A-Z]+\s+#.*$")


def _resolve_vi_voice(requested: str) -> str:
    """If the requested Vi voice is not installed, fall back to plain Linh.

    Mirrors the exact-match logic in scripts/speak.sh: strip locale/comment
    suffix from each `say -v ?` line, then match the requested name exactly.
    """
    try:
        result = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return "Linh"
    names = {
        _VOICE_LINE_LOCALE_RE.sub("", line).strip()
        for line in result.stdout.splitlines()
    }
    return requested if requested in names else "Linh"


def transcribe(audio_path: Path, model_path: str) -> str:
    """Transcribe an audio file (ogg, wav, m4a…) to English text via whisper-cli.

    Converts the input to 16kHz mono wav via ffmpeg, then runs whisper-cli with
    the given model. Returns the trimmed transcript (may be empty string if
    nothing was detected).

    Caller owns cleanup of `audio_path.parent`; intermediate `_whisper_in.wav`
    and `_whisper_out.txt` are left there (orchestrator wraps each call in a
    `tempfile.TemporaryDirectory`).
    """
    work_dir = audio_path.parent
    wav_path = work_dir / "_whisper_in.wav"
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(audio_path),
        "-ac", "1", "-ar", "16000",
        str(wav_path),
    ])
    out_prefix = work_dir / "_whisper_out"
    # whisper-cli writes <prefix>.txt containing the transcript.
    _run([
        "whisper-cli",
        "-m", model_path,
        "-f", str(wav_path),
        "-otxt",
        "-of", str(out_prefix),
        "-nt",       # no timestamps
        "-l", "en",  # force English
    ])
    txt_path = out_prefix.with_suffix(".txt")
    if not txt_path.exists():
        raise AudioError(f"whisper-cli produced no output: {txt_path}")
    return txt_path.read_text(encoding="utf-8").strip()
