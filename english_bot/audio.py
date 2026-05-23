"""Subprocess wrappers for macOS audio I/O + optional ElevenLabs TTS.

Pipeline:
  - synthesize_en/vi: if ELEVENLABS_API_KEY is set → try ElevenLabs first
    (Adam voice via multilingual model — unified Vi+En voice with English
    accent on English words). On any failure (auth, quota, network),
    silently fall back to:
       `say -o aiff` → `ffmpeg → ogg/opus`  (Telegram-friendly)
  - transcribe: incoming ogg → `ffmpeg → 16kHz mono wav` → `whisper-cli` → text

No live mic capture (Telegram delivers pre-recorded voice notes), so sox/rec
is NOT used here. The terminal scripts `speak.sh` and `record.sh` stay
untouched for the slash-command flow.
"""
import logging
import os
import re
import subprocess
from pathlib import Path

import httpx

log = logging.getLogger(__name__)


class AudioError(RuntimeError):
    """Raised when an audio subprocess fails."""


class ElevenLabsError(RuntimeError):
    """Raised when an ElevenLabs API call fails (auth, quota, network, etc)."""


# Adam — popular ElevenLabs preset voice ID. Override via ELEVENLABS_VOICE_ID env.
_ELEVENLABS_DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
# Multilingual v2 handles Vi + En with a single voice. Override via ELEVENLABS_MODEL.
_ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def synthesize_en(text: str, work_dir: Path, voice: str = "Samantha",
                  rate: int = 140) -> Path:
    """Render plain English to an Opus-in-OGG file.

    If ELEVENLABS_API_KEY is set, try ElevenLabs (Adam by default) first.
    Otherwise — or on any ElevenLabs failure (quota exhausted, network,
    auth) — fall back to macOS `say` + ffmpeg.

    Args:
        text: English text to synthesize (no backtick splitting).
        work_dir: existing directory for intermediate + output files.
            Caller owns cleanup; the intermediate .aiff is intentionally
            left in work_dir (don't add unlink() here — synthesize_vi in
            Task 6 keeps per-chunk .aiff files in the same dir for concat).
        voice: macOS voice name for `say` fallback (default Samantha).
        rate: words per minute for `say` fallback (default 140 — slow for
            listening practice). Ignored by ElevenLabs.

    Returns:
        Path to the .ogg file inside work_dir.
    """
    el = _try_elevenlabs(text, work_dir)
    if el is not None:
        return el

    aiff_path = work_dir / "en.aiff"
    ogg_path = work_dir / "en.ogg"
    _run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff_path), text])
    _aiff_to_ogg(aiff_path, ogg_path)
    return ogg_path


def _try_elevenlabs(text: str, work_dir: Path) -> Path | None:
    """Try to synthesize via ElevenLabs. Return Path on success, None on
    any failure (caller falls back to macOS `say`).

    Reads `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL`
    from env. If `ELEVENLABS_API_KEY` is empty/missing, returns None
    immediately without logging (assumed: user opted out of ElevenLabs).
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return None
    voice_id = (
        os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
        or _ELEVENLABS_DEFAULT_VOICE_ID
    )
    model_id = (
        os.environ.get("ELEVENLABS_MODEL", "").strip()
        or _ELEVENLABS_DEFAULT_MODEL
    )
    try:
        return _synthesize_via_elevenlabs(
            text, work_dir, api_key=api_key, voice_id=voice_id, model_id=model_id,
        )
    except Exception as e:
        log.warning(
            "elevenlabs failed (falling back to macOS say): %s", e,
        )
        return None


def _synthesize_via_elevenlabs(
    text: str,
    work_dir: Path,
    *,
    api_key: str,
    voice_id: str,
    model_id: str,
) -> Path:
    """Call ElevenLabs TTS and return Path to an ogg/opus file.

    Strips backticks before sending (they're a Telegram-display convention
    from Claude; Adam doesn't need them — multilingual model handles
    Vi + English with a single voice). Raises ElevenLabsError on any
    non-2xx response or network failure.
    """
    clean = text.replace("`", "").strip()
    if not clean:
        raise ElevenLabsError("empty text after stripping backticks")

    url = f"{_ELEVENLABS_BASE_URL}/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": clean,
        "model_id": model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        r = httpx.post(url, headers=headers, json=payload, timeout=30.0)
    except httpx.HTTPError as e:
        raise ElevenLabsError(f"network: {e}") from e

    if r.status_code == 401:
        raise ElevenLabsError("auth failed (check ELEVENLABS_API_KEY)")
    if r.status_code in (402, 429):
        raise ElevenLabsError(
            f"quota/rate exhausted (HTTP {r.status_code}) — falling back to `say`"
        )
    if r.status_code >= 400:
        raise ElevenLabsError(f"HTTP {r.status_code}: {r.text[:200]}")

    mp3_path = work_dir / "el.mp3"
    mp3_path.write_bytes(r.content)

    ogg_path = work_dir / "el.ogg"
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(mp3_path),
        "-c:a", "libopus", "-b:a", "48k",
        str(ogg_path),
    ])
    return ogg_path


def _aiff_to_ogg(aiff_path: Path, ogg_path: Path) -> None:
    """Convert macOS `say` aiff → Opus-in-OGG, trimming silence at both ends.

    `say` leaves ~50–100 ms of silence at the start and end of every clip,
    which produces an audible gap when synthesize_vi concatenates Linh ↔
    Samantha chunks. We strip those silences via the `silenceremove`
    filter (areverse trick to also process the tail). Single-chunk paths
    benefit too — voice messages on Telegram now start without dead air.
    """
    silence_trim = (
        "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-40dB:detection=peak,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-40dB:detection=peak,"
        "areverse"
    )
    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(aiff_path),
        "-af", silence_trim,
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
    """Render Vi text (possibly mixed with English in backticks) to ogg.

    If ELEVENLABS_API_KEY is set, try ElevenLabs first — a single multilingual
    voice (Adam by default) reads the whole sentence with proper accents on
    each language. On any failure (quota exhausted, network), fall back to
    bilingual macOS `say`: Vi chunks → vi_voice (Linh), English chunks inside
    backticks → en_voice (Samantha), concatenated via ffmpeg.

    Raises AudioError if the input has an odd number of backticks (malformed)
    AND we're on the `say` fallback path.
    """
    el = _try_elevenlabs(text, work_dir)
    if el is not None:
        return el

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
