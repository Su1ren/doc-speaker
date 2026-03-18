# doc-speaker

PDF 内容摘取转有声阅读工具

A command-line tool that splits a long PDF by chapters, extracts the text from each chapter, and converts it to speech using Microsoft Edge's free neural TTS voices.  You can let the tool run in the background while you focus on other work.

---

## Features

| Feature | Details |
|---|---|
| **Chapter detection** | Reads PDF bookmarks/outline first; falls back to heuristic pattern matching for Chinese (第N章/节/篇) and English (Chapter N, Part N, Section N) headings |
| **PDF splitting** | Writes one PDF per detected chapter (or the whole document if no chapters are found) |
| **Text extraction** | Extracts and cleans plain text from any PDF file |
| **TTS synthesis** | Converts text to MP3 via edge-tts — no API key required; supports Chinese, English, Japanese, and [many other languages](https://learn.microsoft.com/azure/ai-services/speech-service/language-support) |
| **Full pipeline** | One command to split → extract → synthesise all chapters |

---

## Requirements

- Python 3.10+
- Internet connection (edge-tts calls the Microsoft Edge Read-Aloud service)

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Usage

### Split a PDF by chapters

```bash
python main.py split reference.pdf -o chapters/
```

### Extract plain text from a chapter (or any PDF)

```bash
python main.py extract chapters/001_第一章_概述.pdf -o chapters/001.txt
# or print to stdout
python main.py extract chapters/001_第一章_概述.pdf
```

### Convert a PDF or text file to speech

```bash
# auto-detect language as Chinese (default)
python main.py speak chapters/001_第一章_概述.pdf

# specify a voice and a faster speaking rate
python main.py speak chapters/001_第一章_概述.pdf -v zh-CN-YunxiNeural -r "+20%"

# convert a plain-text file
python main.py speak chapters/001.txt -l en
```

### Full pipeline — split, extract, and synthesise in one step

```bash
python main.py pipeline reference.pdf -o output/
```

Output layout:

```
output/
    chapters/   ← per-chapter PDF files
    text/       ← plain-text counterparts
    audio/      ← MP3 files ready to play
```

Use `--text-only` to skip TTS (useful for large documents where you want to review the text first):

```bash
python main.py pipeline reference.pdf -o output/ --text-only
```

### List available TTS voices

```bash
# all voices
python main.py list-voices

# filter to Chinese voices
python main.py list-voices -l zh
```

---

## Common options

| Option | Default | Description |
|---|---|---|
| `-l / --lang` | `zh` | Language code for voice selection (`zh`, `en`, `ja`, `ko`, …) |
| `-v / --voice` | auto | Explicit edge-tts voice name (overrides `--lang`) |
| `-r / --rate` | `+0%` | Speaking rate, e.g. `+20%` faster, `-10%` slower |
| `--volume` | `+0%` | Volume adjustment |
| `--max-chars` | `3000` | Max characters per TTS request (long texts are split at sentence boundaries) |

---

## Development

```bash
# run the test suite
python -m pytest tests/ -v
```

---

## Project structure

```
doc-speaker/
├── main.py                 ← CLI entry point
├── requirements.txt
├── src/
│   ├── pdf_splitter.py     ← chapter detection + PDF splitting
│   ├── text_extractor.py   ← text extraction + cleaning
│   └── tts_reader.py       ← TTS synthesis via edge-tts
└── tests/
    ├── test_pdf_splitter.py
    └── test_tts_reader.py
```

