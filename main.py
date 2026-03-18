#!/usr/bin/env python3
"""
doc-speaker – PDF 内容摘取转有声阅读工具

Usage examples
--------------
# Split a 200-page PDF into per-chapter PDFs
python main.py split reference.pdf -o chapters/

# Extract plain text from one chapter
python main.py extract chapters/001_第一章.pdf -o chapters/001.txt

# Convert a chapter PDF directly to speech
python main.py speak chapters/001_第一章.pdf -l zh

# One-shot pipeline: split → extract → TTS
python main.py pipeline reference.pdf -o output/

# List available TTS voices (filter to Chinese)
python main.py list-voices -l zh
"""

import os
import sys
from typing import Optional

import click
from tqdm import tqdm

from src.pdf_splitter import detect_chapters, split_pdf_by_chapters
from src.text_extractor import extract_text, extract_text_to_file
from src.tts_reader import DEFAULT_VOICES, pdf_to_speech, text_to_speech


@click.group()
@click.version_option("0.1.0")
def cli() -> None:
    """doc-speaker: split PDF by chapters and convert to speech."""


# ---------------------------------------------------------------------------
# split
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("pdf_path")
@click.option(
    "-o", "--output-dir",
    default="chapters",
    show_default=True,
    help="Directory to write chapter PDFs into.",
)
def split(pdf_path: str, output_dir: str) -> None:
    """Split PDF_PATH into per-chapter PDF files."""
    if not os.path.exists(pdf_path):
        click.echo(f"Error: file not found – {pdf_path}", err=True)
        sys.exit(1)

    click.echo(f"Detecting chapters in {pdf_path} …")
    chapters = detect_chapters(pdf_path)

    if not chapters:
        click.echo("No chapters detected – saving the full document as one file.")
    else:
        click.echo(f"Found {len(chapters)} chapter(s):")
        for i, ch in enumerate(chapters, 1):
            click.echo(f"  {i:>3}. {ch['title']}  (page {ch['page'] + 1})")

    click.echo(f"\nSplitting into {output_dir}/ …")
    output_files = split_pdf_by_chapters(pdf_path, output_dir, chapters)

    click.echo(f"Done – created {len(output_files)} file(s):")
    for f in output_files:
        click.echo(f"  {f}")


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("pdf_path")
@click.option(
    "-o", "--output",
    default=None,
    help="Output text file (default: print to stdout).",
)
@click.option(
    "--no-clean",
    is_flag=True,
    help="Skip whitespace normalisation.",
)
def extract(pdf_path: str, output: Optional[str], no_clean: bool) -> None:
    """Extract plain text from PDF_PATH."""
    if not os.path.exists(pdf_path):
        click.echo(f"Error: file not found – {pdf_path}", err=True)
        sys.exit(1)

    if output:
        extract_text_to_file(pdf_path, output, clean=not no_clean)
        click.echo(f"Text saved to {output}")
    else:
        click.echo(extract_text(pdf_path, clean=not no_clean))


# ---------------------------------------------------------------------------
# speak
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("input_path", metavar="PDF_OR_TEXT")
@click.option("-o", "--output", default=None, help="Output MP3 file path.")
@click.option(
    "-v", "--voice",
    default=None,
    help="Explicit edge-tts voice name (see list-voices).",
)
@click.option(
    "-l", "--lang",
    default="zh",
    show_default=True,
    help="Language code for default voice selection.",
)
@click.option("-r", "--rate", default="+0%", show_default=True,
              help="Speaking rate adjustment, e.g. +10%, -20%.")
@click.option("--volume", default="+0%", show_default=True,
              help="Volume adjustment, e.g. +10%, -20%.")
@click.option(
    "--max-chars",
    default=3000,
    show_default=True,
    help="Max characters per audio segment.",
)
def speak(
    input_path: str,
    output: Optional[str],
    voice: Optional[str],
    lang: str,
    rate: str,
    volume: str,
    max_chars: int,
) -> None:
    """Convert PDF_OR_TEXT to speech (MP3)."""
    if not os.path.exists(input_path):
        click.echo(f"Error: file not found – {input_path}", err=True)
        sys.exit(1)

    base = os.path.splitext(input_path)[0]
    if output is None:
        output = f"{base}.mp3"

    click.echo(f"Converting {input_path} to speech …")

    if input_path.lower().endswith(".pdf"):
        files = pdf_to_speech(
            input_path, output,
            voice=voice, lang=lang, rate=rate, volume=volume,
            max_chars=max_chars,
        )
    else:
        with open(input_path, encoding="utf-8") as fh:
            text = fh.read()
        files = [text_to_speech(text, output, voice=voice, lang=lang,
                                rate=rate, volume=volume)]

    click.echo(f"Done – generated {len(files)} audio file(s):")
    for f in files:
        click.echo(f"  {f}")


# ---------------------------------------------------------------------------
# list-voices
# ---------------------------------------------------------------------------

@cli.command("list-voices")
@click.option(
    "-l", "--lang",
    default=None,
    help="Filter voices by locale prefix (e.g. zh, en, ja).",
)
def list_voices(lang: Optional[str]) -> None:
    """List available edge-tts voices."""
    import asyncio
    import edge_tts

    async def _get() -> list:
        return await edge_tts.list_voices()

    voices = asyncio.run(_get())

    click.echo(f"{'Voice':<42} {'Locale':<12} Gender")
    click.echo("-" * 62)
    for v in voices:
        short = v["ShortName"]
        locale = v["Locale"]
        gender = v["Gender"]
        if lang and not locale.lower().startswith(lang.lower()):
            continue
        click.echo(f"{short:<42} {locale:<12} {gender}")


# ---------------------------------------------------------------------------
# pipeline  (split → extract → TTS)
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("pdf_path")
@click.option(
    "-o", "--output-dir",
    default="output",
    show_default=True,
    help="Root output directory.",
)
@click.option("-v", "--voice", default=None, help="Explicit voice name.")
@click.option("-l", "--lang", default="zh", show_default=True,
              help="Language code.")
@click.option("-r", "--rate", default="+0%", show_default=True,
              help="Speaking rate.")
@click.option("--volume", default="+0%", show_default=True,
              help="Volume level.")
@click.option("--max-chars", default=3000, show_default=True,
              help="Max characters per audio segment.")
@click.option("--text-only", is_flag=True,
              help="Stop after text extraction (skip TTS).")
def pipeline(
    pdf_path: str,
    output_dir: str,
    voice: Optional[str],
    lang: str,
    rate: str,
    volume: str,
    max_chars: int,
    text_only: bool,
) -> None:
    """Full pipeline: split PDF by chapters, extract text, synthesise speech.

    Output layout::

        <output-dir>/
            chapters/   ← per-chapter PDF files
            text/       ← plain-text counterparts
            audio/      ← MP3 files (skipped with --text-only)
    """
    if not os.path.exists(pdf_path):
        click.echo(f"Error: file not found – {pdf_path}", err=True)
        sys.exit(1)

    chapters_dir = os.path.join(output_dir, "chapters")
    text_dir = os.path.join(output_dir, "text")
    audio_dir = os.path.join(output_dir, "audio")

    # -- Step 1: split -------------------------------------------------------
    click.echo("[1/3] Detecting chapters and splitting PDF …")
    chapter_files = split_pdf_by_chapters(pdf_path, chapters_dir)
    click.echo(f"      {len(chapter_files)} chapter file(s) → {chapters_dir}/")

    # -- Step 2: extract text ------------------------------------------------
    click.echo("[2/3] Extracting text …")
    os.makedirs(text_dir, exist_ok=True)
    text_files = []
    for cf in tqdm(chapter_files, desc="  extract", unit="file"):
        base = os.path.splitext(os.path.basename(cf))[0]
        txt_path = os.path.join(text_dir, f"{base}.txt")
        extract_text_to_file(cf, txt_path)
        text_files.append(txt_path)
    click.echo(f"      {len(text_files)} text file(s) → {text_dir}/")

    if text_only:
        click.echo("Done (--text-only).")
        return

    # -- Step 3: TTS ---------------------------------------------------------
    click.echo("[3/3] Synthesising speech …")
    os.makedirs(audio_dir, exist_ok=True)
    audio_files = []
    for tf in tqdm(text_files, desc="  TTS  ", unit="file"):
        with open(tf, encoding="utf-8") as fh:
            text = fh.read()
        if not text.strip():
            continue
        base = os.path.splitext(os.path.basename(tf))[0]
        audio_path = os.path.join(audio_dir, f"{base}.mp3")
        generated = text_to_speech(
            text, audio_path, voice=voice, lang=lang, rate=rate, volume=volume
        )
        audio_files.append(generated)
    click.echo(f"      {len(audio_files)} audio file(s) → {audio_dir}/")

    click.echo("Pipeline complete!")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
