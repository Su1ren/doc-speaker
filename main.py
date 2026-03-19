#!/usr/bin/env python3
"""
doc-speaker – PDF 内容摘取转有声阅读工具

Usage examples
--------------
# Split a 200-page PDF into per-chapter PDFs
python main.py split reference.pdf -o chapters/

# Extract Markdown from one chapter
python main.py extract chapters/001_第一章.pdf -o chapters/001.md

# Convert a chapter PDF directly to speech
python main.py speak chapters/001_第一章.pdf -l zh

# One-shot pipeline: split → extract → prompt → TTS
python main.py pipeline reference.pdf -o output/ --rewrite

# List available TTS voices (filter to Chinese)
python main.py list-voices -l zh
"""

import os
import sys
from typing import Optional

import click
from tqdm import tqdm

from src.pdf_splitter import detect_chapters, split_pdf_by_chapters
from src.text_extractor import (
    extract_markdown,
    extract_markdown_to_file,
    extract_text,
    extract_text_to_file,
    markdown_to_plaintext,
)
from src.tts_reader import (
    DEFAULT_VOICES,
    TTSServiceError,
    _split_text,
    pdf_to_speech,
    text_to_speech,
)
from src.prompt_builder import build_speech_prompt
from src.llm_rewriter import LLMConfigError, LLMServiceError, rewrite_with_openai
from src.cosyvoice_adapter import CosyVoiceError, cosyvoice_tts


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
@click.option(
    "-f", "--format",
    "out_format",
    type=click.Choice(["md", "text"]),
    default="md",
    show_default=True,
    help="Extraction format (markdown or legacy plain text).",
)
def extract(pdf_path: str, output: Optional[str], no_clean: bool, out_format: str) -> None:
    """Extract content from PDF_PATH as Markdown (default) or plain text."""
    if not os.path.exists(pdf_path):
        click.echo(f"Error: file not found – {pdf_path}", err=True)
        sys.exit(1)

    if out_format == "md":
        if output:
            extract_markdown_to_file(pdf_path, output)
            click.echo(f"Markdown saved to {output}")
        else:
            click.echo(extract_markdown(pdf_path))
    else:
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

    try:
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
    except TTSServiceError as exc:
        click.echo(f"TTS service error: {exc}", err=True)
        sys.exit(1)

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
              help="Stop after markdown + prompt generation (skip TTS).")
@click.option(
    "--rewrite",
    is_flag=True,
    help="Use configured LLM to rewrite Markdown into SSML before TTS.",
)
@click.option(
    "--llm-model",
    default=None,
    help="Model name for LLM rewrite (default: OPENAI_MODEL env or gpt-4o-mini).",
)
@click.option(
    "--tts-provider",
    type=click.Choice(["edge", "cosyvoice"]),
    default="edge",
    show_default=True,
    help="TTS engine to use for the final audio.",
)
def pipeline(
    pdf_path: str,
    output_dir: str,
    voice: Optional[str],
    lang: str,
    rate: str,
    volume: str,
    max_chars: int,
    text_only: bool,
    rewrite: bool,
    llm_model: Optional[str],
    tts_provider: str,
) -> None:
    """Full pipeline: split PDF by chapters, extract Markdown, build prompts, synthesise speech.

    Output layout::

        <output-dir>/
            chapters/   ← per-chapter PDF files
            markdown/   ← Markdown counterparts
            prompts/    ← LLM prompts ready to send
            scripts/    ← LLM rewrite outputs (SSML) when --rewrite is used
            audio/      ← MP3 files (skipped with --text-only)
    """
    if not os.path.exists(pdf_path):
        click.echo(f"Error: file not found – {pdf_path}", err=True)
        sys.exit(1)

    chapters_dir = os.path.join(output_dir, "chapters")
    markdown_dir = os.path.join(output_dir, "markdown")
    prompts_dir = os.path.join(output_dir, "prompts")
    scripts_dir = os.path.join(output_dir, "scripts")
    audio_dir = os.path.join(output_dir, "audio")

    # -- Step 1: split -------------------------------------------------------
    click.echo("[1/4] Detecting chapters and splitting PDF …")
    chapter_files = split_pdf_by_chapters(pdf_path, chapters_dir)
    click.echo(f"      {len(chapter_files)} chapter file(s) → {chapters_dir}/")

    # -- Step 2: extract Markdown -------------------------------------------
    click.echo("[2/4] Extracting Markdown …")
    os.makedirs(markdown_dir, exist_ok=True)
    md_files = []
    for cf in tqdm(chapter_files, desc="  extract", unit="file"):
        base = os.path.splitext(os.path.basename(cf))[0]
        md_path = os.path.join(markdown_dir, f"{base}.md")
        extract_markdown_to_file(cf, md_path)
        md_files.append(md_path)
    click.echo(f"      {len(md_files)} markdown file(s) → {markdown_dir}/")

    # -- Step 3: build prompts / rewrite ------------------------------------
    click.echo("[3/4] Building LLM prompts …")
    os.makedirs(prompts_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)
    script_files = []
    for md_file in tqdm(md_files, desc="  prompt", unit="file"):
        with open(md_file, encoding="utf-8") as fh:
            md_content = fh.read()

        prompt_text = build_speech_prompt(md_content, locale=lang)
        prompt_path = os.path.join(prompts_dir, os.path.basename(md_file))
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(prompt_text)

        if rewrite:
            try:
                script_text = rewrite_with_openai(
                    md_content, model=llm_model, locale=lang
                )
            except (LLMConfigError, LLMServiceError) as exc:
                click.echo(f"LLM rewrite failed for {md_file}: {exc}", err=True)
                sys.exit(1)

            script_path = os.path.join(
                scripts_dir, f"{os.path.splitext(os.path.basename(md_file))[0]}.ssml"
            )
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(script_text)
            script_files.append(script_path)
    click.echo(f"      Prompts → {prompts_dir}/")
    if rewrite:
        click.echo(f"      {len(script_files)} SSML script(s) → {scripts_dir}/")

    if text_only:
        click.echo("Done (--text-only).")
        return

    # -- Step 4: TTS ---------------------------------------------------------
    click.echo("[4/4] Synthesising speech …")
    os.makedirs(audio_dir, exist_ok=True)
    audio_files = []
    sources = script_files if script_files else md_files

    for source in tqdm(sources, desc="  TTS  ", unit="file"):
        with open(source, encoding="utf-8") as fh:
            content = fh.read()
        if not content.strip():
            continue

        if script_files:
            speak_text = content
        else:
            speak_text = markdown_to_plaintext(content)

        chunks = _split_text(speak_text, max_chars)
        base_name = os.path.splitext(os.path.basename(source))[0]

        for i, chunk in enumerate(chunks, start=1):
            suffix = ".mp3" if len(chunks) == 1 else f"_part{i:03d}.mp3"
            audio_path = os.path.join(audio_dir, f"{base_name}{suffix}")

            if tts_provider == "edge":
                try:
                    generated = text_to_speech(
                        chunk, audio_path, voice=voice, lang=lang, rate=rate, volume=volume
                    )
                    audio_files.append(generated)
                except TTSServiceError as exc:
                    click.echo(f"TTS service error while processing {source}: {exc}", err=True)
                    sys.exit(1)
            else:
                ssml_chunk = chunk if "<speak" in chunk else f"<speak>{chunk}</speak>"
                try:
                    generated = cosyvoice_tts(ssml_chunk, audio_path, speaker=voice or "cosyvoice")
                    audio_files.append(generated)
                except CosyVoiceError as exc:
                    click.echo(f"CosyVoice error while processing {source}: {exc}", err=True)
                    sys.exit(1)
    click.echo(f"      {len(audio_files)} audio file(s) → {audio_dir}/")

    click.echo("Pipeline complete!")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
