"""
text_extractor.py – Extract and optionally clean text from PDF files.
"""

import re
from typing import Optional

import fitz  # PyMuPDF


def extract_text(pdf_path: str, clean: bool = True) -> str:
    """Extract all text from *pdf_path*.

    Args:
        pdf_path: Path to the PDF file.
        clean:    When *True* (default) the raw text is normalised:
                  redundant whitespace collapsed, control characters removed.

    Returns:
        The full extracted text as a single string.
    """
    doc = fitz.open(pdf_path)
    try:
        page_texts = [page.get_text() for page in doc]
    finally:
        doc.close()

    text = "\n".join(page_texts)
    return _clean_text(text) if clean else text


def _clean_text(text: str) -> str:
    """Normalise raw PDF text."""
    text = re.sub(r"[\f\r]", "\n", text)          # form feeds → newlines
    text = re.sub(r"[ \t]+", " ", text)            # collapse horizontal space
    text = re.sub(r"\n{3,}", "\n\n", text)         # collapse blank lines
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def extract_text_to_file(
    pdf_path: str,
    output_path: str,
    clean: bool = True,
) -> str:
    """Extract text from *pdf_path* and write it to *output_path*.

    Returns the *output_path* so callers can chain calls conveniently.
    """
    text = extract_text(pdf_path, clean=clean)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return output_path
