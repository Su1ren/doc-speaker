"""
text_extractor.py – Extract Markdown (and legacy text) from PDF files.
"""

import re

import fitz  # PyMuPDF

# Heuristics for recognising headings when rebuilding Markdown.
_HEADING_PATTERNS = [
    r"^第[一二三四五六七八九十0-9]+[章节篇节]\b",
    r"^Chapter\s+\d+",
    r"^Section\s+\d+",
    r"^[A-Z][\w\s]{0,40}$",
]
_BULLET_PREFIXES = ("•", "·", "▪", "◦")


# ---------------------------------------------------------------------------
# Legacy plain-text extraction (kept for backwards compatibility)
# ---------------------------------------------------------------------------

def extract_text(pdf_path: str, clean: bool = True) -> str:
    """Extract all text from *pdf_path* as plain text."""
    doc = fitz.open(pdf_path)
    try:
        page_texts = [page.get_text() for page in doc]
    finally:
        doc.close()

    text = "\n".join(page_texts)
    return _clean_text(text) if clean else text


def extract_text_to_file(
    pdf_path: str,
    output_path: str,
    clean: bool = True,
) -> str:
    """Extract text from *pdf_path* and write it to *output_path*."""
    text = extract_text(pdf_path, clean=clean)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return output_path


# ---------------------------------------------------------------------------
# Markdown-first extraction
# ---------------------------------------------------------------------------

def extract_markdown(pdf_path: str) -> str:
    """Extract Markdown from *pdf_path*, keeping headings and tables where possible."""
    doc = fitz.open(pdf_path)
    blocks: list[str] = []
    try:
        for page in doc:
            blocks.extend(_page_to_markdown_blocks(page))
    finally:
        doc.close()

    # Keep page order; drop empties and deduplicate excessive blanks.
    content = "\n\n".join([blk for blk in blocks if blk.strip()])
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return content


def extract_markdown_to_file(pdf_path: str, output_path: str) -> str:
    """Extract Markdown from *pdf_path* and save it to *output_path*."""
    markdown = extract_markdown(pdf_path)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    return output_path


def markdown_to_plaintext(markdown: str) -> str:
    """Strip lightweight Markdown markers so TTS engines read clean text."""
    text = markdown
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)  # flatten table bars
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _page_to_markdown_blocks(page) -> list[str]:
    """Convert a single page into an ordered list of Markdown fragments."""
    items = []

    # Text blocks (ordered by top-left position)
    for x0, y0, x1, y1, text, block_no, block_type in page.get_text("blocks"):
        if block_type != 0:  # skip images/other block types
            continue
        md = _block_to_markdown(text)
        if md:
            items.append({"y": y0, "x": x0, "type": "text", "content": md})

    # Tables (when PyMuPDF can detect them)
    try:
        tables = page.find_tables()
    except Exception:
        tables = []

    for table in tables:
        md_table = _table_to_markdown(table.extract())
        if md_table.strip():
            y0 = table.bbox[1] if hasattr(table, "bbox") else 0
            items.append({"y": y0, "x": 0, "type": "table", "content": md_table})

    items.sort(key=lambda it: (round(it["y"], 2), round(it["x"], 2), it["type"]))
    return [it["content"] for it in items]


def _block_to_markdown(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    lines = [ln for ln in cleaned.splitlines() if ln.strip()]
    if not lines:
        return ""

    first_line = lines[0].strip()
    if len(lines) == 1 and first_line.lstrip().startswith(_BULLET_PREFIXES + ("-", "*")):
        return _normalise_bullet_line(first_line)

    if _looks_like_heading(first_line):
        return f"## {first_line}"

    if _looks_like_list(lines):
        bullets = [_normalise_bullet_line(ln) for ln in lines]
        return "\n".join(bullets)

    normalised_lines = [_normalise_bullet_line(ln) if ln.lstrip().startswith(_BULLET_PREFIXES) else ln for ln in lines]
    return "\n".join(normalised_lines)


def _looks_like_heading(line: str) -> bool:
    if len(line) > 80:
        return False
    return any(re.match(pat, line, flags=re.IGNORECASE) for pat in _HEADING_PATTERNS)


def _looks_like_list(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False

    bullet_lines = sum(
        1 for ln in lines if ln.lstrip().startswith(_BULLET_PREFIXES + ("-", "*"))
    )
    return bullet_lines >= max(2, len(lines) // 2)


def _normalise_bullet_line(line: str) -> str:
    stripped = line.lstrip()
    stripped = re.sub(rf"^([{''.join(_BULLET_PREFIXES)}])", "-", stripped)
    return stripped if stripped.startswith(("-", "*")) else f"- {stripped}"


def _table_to_markdown(rows: list[list[str]]) -> str:
    """Convert a table (list-of-lists) into Markdown format."""
    if not rows:
        return ""

    normalised = [
        [(cell or "").replace("\n", " ").strip() for cell in row] for row in rows
    ]
    header = normalised[0]
    col_count = len(header)
    header_line = "| " + " | ".join(header) + " |"
    separator = "| " + " | ".join(["---"] * col_count) + " |"

    body_rows = normalised[1:] or [["" for _ in range(col_count)]]
    body_lines = [
        "| " + " | ".join(row + [""] * (col_count - len(row))) + " |"
        for row in body_rows
    ]
    return "\n".join([header_line, separator, *body_lines])


def _clean_text(text: str) -> str:
    """Normalise raw PDF text."""
    text = re.sub(r"[\f\r]", "\n", text)          # form feeds → newlines
    text = re.sub(r"[ \t]+", " ", text)            # collapse horizontal space
    text = re.sub(r"\n{3,}", "\n\n", text)         # collapse blank lines
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()
