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
                  en_voice: str = "Samantha", rate: int = 170) -> Path:
    """Render Vi text with `english` backtick-bracketed chunks read by en_voice.

    Bilingual split: text outside backticks → vi_voice; text inside → en_voice.
    Each chunk is `say -o` to its own aiff, converted to ogg, then concatenated
    via ffmpeg into one final ogg. If only one chunk exists, no concat.
    Raises AudioError if the input has an odd number of backticks (malformed).
    """
    chunks = _split_backticks(text)
    if not chunks:
        raise AudioError("synthesize_vi got empty text")

    resolved_vi_voice = _resolve_vi_voice(vi_voice)

    if len(chunks) == 1:
        is_en, chunk_text = chunks[0]
        voice = en_voice if is_en else resolved_vi_voice
        aiff = work_dir / "vi.aiff"
        ogg = work_dir / "vi.ogg"
        _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), chunk_text])
        _aiff_to_ogg(aiff, ogg)
        return ogg

    ogg_parts: list[Path] = []
    for i, (is_en, chunk_text) in enumerate(chunks):
        voice = en_voice if is_en else resolved_vi_voice
        aiff = work_dir / f"vi_{i}.aiff"
        ogg = work_dir / f"vi_{i}.ogg"
        _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), chunk_text])
        _aiff_to_ogg(aiff, ogg)
        ogg_parts.append(ogg)

    return _concat_oggs(ogg_parts, work_dir / "vi.ogg")


def _split_backticks(text: str) -> list[tuple[bool, str]]:
    """Split on backticks. Returns [(is_english, chunk)]. Trims whitespace,
    skips empty chunks. Odd-indexed parts (after split) are English.

    Raises AudioError if `text` contains an odd number of backticks
    (malformed input — would misclassify the unmatched tail as English).
    """
    if text.count("`") % 2 != 0:
        raise AudioError(
            f"synthesize_vi: unmatched backtick in text (count={text.count('`')})"
        )
    parts = text.split("`")
    out: list[tuple[bool, str]] = []
    for i, raw in enumerate(parts):
        chunk = raw.strip()
        if not chunk:
            continue
        out.append((i % 2 == 1, chunk))
    return out


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


def _concat_oggs(parts: list[Path], out_path: Path) -> Path:
    """Use ffmpeg concat demuxer to join multiple oggs in order."""
    listfile = out_path.with_suffix(".list")
    listfile.write_text("".join(f"file '{p}'\n" for p in parts))
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(listfile),
        "-c", "copy",
        str(out_path),
    ])
    return out_path


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
