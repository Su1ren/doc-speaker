"""
tts_reader.py – Convert text (or PDF content) to speech using edge-tts.

edge-tts wraps the Microsoft Edge Read-Aloud service, which is free,
requires no API key, supports Chinese / Japanese / English, and produces
high-quality neural voices.
"""

import asyncio
import os
import re
from typing import List, Optional

import edge_tts

# ---------------------------------------------------------------------------
# Default voice map – keyed by lowercase language code prefix.
# Run `python -m edge_tts --list-voices` to see all available voices.
# ---------------------------------------------------------------------------
DEFAULT_VOICES: dict = {
    "zh":    "zh-CN-XiaoxiaoNeural",   # Mandarin (Simplified)
    "zh-cn": "zh-CN-XiaoxiaoNeural",
    "zh-tw": "zh-TW-HsiaoChenNeural",  # Mandarin (Traditional)
    "en":    "en-US-AriaNeural",        # English (US)
    "ja":    "ja-JP-NanamiNeural",      # Japanese
    "ko":    "ko-KR-SunHiNeural",       # Korean
}


# ---------------------------------------------------------------------------
# Internal async core
# ---------------------------------------------------------------------------

async def _synthesise(
    text: str,
    output_path: str,
    voice: str,
    rate: str,
    volume: str,
) -> None:
    """Write an MP3 file for *text* using the given *voice*."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(output_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def text_to_speech(
    text: str,
    output_path: str,
    voice: Optional[str] = None,
    lang: str = "zh",
    rate: str = "+0%",
    volume: str = "+0%",
) -> str:
    """Convert *text* to an MP3 file at *output_path*.

    Args:
        text:        Text to synthesise.
        output_path: Destination MP3 path (parent directories are created
                     automatically).
        voice:       Explicit edge-tts voice name.  When *None* a sensible
                     default for *lang* is chosen.
        lang:        Language code used for voice selection when *voice* is
                     *None* (e.g. ``"zh"``, ``"en"``, ``"ja"``).
        rate:        Speaking-rate adjustment string (e.g. ``"+10%"``).
        volume:      Volume adjustment string (e.g. ``"-20%"``).

    Returns:
        The *output_path* that was written.
    """
    if voice is None:
        voice = DEFAULT_VOICES.get(lang.lower(), DEFAULT_VOICES["zh"])

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    asyncio.run(_synthesise(text, output_path, voice, rate, volume))
    return output_path


def pdf_to_speech(
    pdf_path: str,
    output_path: str,
    voice: Optional[str] = None,
    lang: str = "zh",
    rate: str = "+0%",
    volume: str = "+0%",
    max_chars: int = 3000,
) -> List[str]:
    """Extract text from *pdf_path* and synthesise it to one or more MP3 files.

    Long texts are split at sentence boundaries so that each audio segment
    stays within *max_chars* characters (preventing edge-tts timeouts).

    Args:
        pdf_path:    Source PDF file.
        output_path: Base path for the output MP3 (extension is replaced with
                     ``.mp3``).  For multi-part output the parts are named
                     ``<base>_part001.mp3``, ``<base>_part002.mp3``, …
        voice:       Explicit voice name.
        lang:        Language code for default voice selection.
        rate:        Speaking-rate adjustment.
        volume:      Volume adjustment.
        max_chars:   Maximum characters per audio segment.

    Returns:
        List of generated MP3 file paths.
    """
    from src.text_extractor import extract_text  # local import avoids cycles

    text = extract_text(pdf_path)
    if not text:
        return []

    chunks = _split_text(text, max_chars)
    base = os.path.splitext(output_path)[0]
    output_files: List[str] = []

    for i, chunk in enumerate(chunks):
        if len(chunks) == 1:
            chunk_path = f"{base}.mp3"
        else:
            chunk_path = f"{base}_part{i + 1:03d}.mp3"
        text_to_speech(
            chunk, chunk_path, voice=voice, lang=lang, rate=rate, volume=volume
        )
        output_files.append(chunk_path)

    return output_files


def _split_text(text: str, max_chars: int) -> List[str]:
    """Split *text* into chunks ≤ *max_chars* at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    # Split at Chinese / English sentence endings.
    # Use a zero-width lookbehind so the separator position is consumed but no
    # trailing whitespace is dropped; this preserves the original text when
    # the chunks are joined back together.
    sentence_end = re.compile(r"(?<=[。！？.!?])")
    sentences = sentence_end.split(text)

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) > max_chars and current:
            chunks.append("".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence)

    if current:
        chunks.append("".join(current))

    return chunks
