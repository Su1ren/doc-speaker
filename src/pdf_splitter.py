"""
pdf_splitter.py – Detect chapter boundaries in a PDF and split it into
per-chapter PDF files.

Detection strategy (in priority order):
  1. PDF bookmarks / outline (most reliable).
  2. Heuristic text-pattern matching for common Chinese and English
     chapter-heading styles.
"""

import os
import re
from typing import Dict, List, Optional

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_bookmarks(doc: fitz.Document) -> List[Dict]:
    """Return top-level bookmark entries as chapter records.

    Each record contains:
      ``title`` – heading text
      ``page``  – 0-indexed page number
    """
    toc = doc.get_toc()  # [[level, title, page_1indexed], ...]
    return [
        {"title": title, "page": page - 1}
        for level, title, page in toc
        if level == 1
    ]


# Patterns that match the first token(s) of a chapter heading line.
_HEADING_PATTERNS: List[re.Pattern] = [
    re.compile(r"^第[零一二三四五六七八九十百千\d]+[章节篇部]"),  # 第一章 …
    re.compile(r"^Chapter\s+\d+", re.IGNORECASE),               # Chapter 1 …
    re.compile(r"^Part\s+\d+", re.IGNORECASE),                  # Part 1 …
    re.compile(r"^Section\s+\d+", re.IGNORECASE),               # Section 1 …
    re.compile(r"^\d+\.\s+\S"),                                  # 1. Title
]


def _detect_chapter_headings(doc: fitz.Document) -> List[Dict]:
    """Heuristic: scan every text block for heading-like lines."""
    chapters: List[Dict] = []
    seen_pages = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        raw = page.get_text("dict")
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = "".join(
                    span["text"] for span in line.get("spans", [])
                ).strip()
                if not line_text:
                    continue
                for pattern in _HEADING_PATTERNS:
                    if pattern.match(line_text):
                        if page_num not in seen_pages:
                            chapters.append({"title": line_text, "page": page_num})
                            seen_pages.add(page_num)
                        break

    return chapters


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_chapters(pdf_path: str) -> List[Dict]:
    """Detect chapter boundaries in *pdf_path*.

    Returns a list of dicts with keys:
      ``title`` – chapter heading string
      ``page``  – 0-indexed start page of the chapter

    Bookmarks take priority; heuristic detection is used as a fallback.
    """
    doc = fitz.open(pdf_path)
    try:
        chapters = _extract_bookmarks(doc)
        if not chapters:
            chapters = _detect_chapter_headings(doc)
    finally:
        doc.close()
    return chapters


def split_pdf_by_chapters(
    pdf_path: str,
    output_dir: str,
    chapters: Optional[List[Dict]] = None,
) -> List[str]:
    """Split *pdf_path* into one PDF file per chapter.

    Args:
        pdf_path:   Path to the source PDF.
        output_dir: Directory that will receive the chapter PDFs (created if
                    it does not exist).
        chapters:   Pre-computed chapter list.  When *None* the list is
                    auto-detected via :func:`detect_chapters`.

    Returns:
        Ordered list of paths to the generated chapter PDF files.  If no
        chapters are detected the whole document is saved as a single file
        named ``full_document.pdf``.
    """
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    if chapters is None:
        chapters = detect_chapters(pdf_path)

    if not chapters:
        out_path = os.path.join(output_dir, "full_document.pdf")
        doc.save(out_path)
        doc.close()
        return [out_path]

    output_files: List[str] = []

    for i, chapter in enumerate(chapters):
        start_page = chapter["page"]
        end_page = (
            chapters[i + 1]["page"] if i + 1 < len(chapters) else total_pages
        )

        title = chapter["title"]
        # Build a filesystem-safe filename that preserves CJK characters.
        safe_title = re.sub(r'[^\w\s\u4e00-\u9fff\-]', "", title).strip()
        safe_title = re.sub(r"\s+", "_", safe_title)
        filename = f"{i + 1:03d}_{safe_title}.pdf"
        out_path = os.path.join(output_dir, filename)

        chapter_doc = fitz.open()
        chapter_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
        chapter_doc.save(out_path)
        chapter_doc.close()
        output_files.append(out_path)

    doc.close()
    return output_files
