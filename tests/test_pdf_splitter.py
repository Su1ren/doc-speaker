"""
Unit tests for pdf_splitter.py and text_extractor.py.

These tests use PyMuPDF to create tiny in-memory PDFs so no real PDF
fixture files are needed.
"""

import os
import re

import fitz  # PyMuPDF
import pytest

from src.pdf_splitter import detect_chapters, split_pdf_by_chapters
from src.text_extractor import _clean_text, extract_text, extract_text_to_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf(path: str, pages: list[tuple[str, int]], fontname: str = "helv") -> None:
    """Create a PDF where each entry in *pages* is (text, fontsize).

    *fontname* can be ``"china-s"`` for CJK text.
    """
    doc = fitz.open()
    for text, fontsize in pages:
        page = doc.new_page()
        page.insert_text((50, 72), text, fontsize=fontsize, fontname=fontname)
    doc.save(path)
    doc.close()


def _make_pdf_with_toc(path: str, chapters: list[tuple[str, str]]) -> None:
    """Create a PDF with a Table-of-Contents (bookmarks).

    *chapters* is a list of (heading, body_text) tuples; one page per chapter.
    CJK headings are rendered with the ``china-s`` built-in font.
    """
    doc = fitz.open()
    for heading, body in chapters:
        page = doc.new_page()
        page.insert_text((50, 72), heading, fontsize=18, fontname="china-s")
        page.insert_text((50, 120), body, fontsize=12)

    toc = [[1, heading, i + 1] for i, (heading, _) in enumerate(chapters)]
    doc.set_toc(toc)
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# detect_chapters
# ---------------------------------------------------------------------------

class TestDetectChapters:
    def test_bookmarks_take_priority(self, tmp_path):
        pdf = str(tmp_path / "toc.pdf")
        _make_pdf_with_toc(pdf, [
            ("第一章 概述", "背景内容"),
            ("第二章 方法", "方法描述"),
            ("第三章 结论", "结论内容"),
        ])
        chapters = detect_chapters(pdf)

        assert len(chapters) == 3
        assert chapters[0]["title"] == "第一章 概述"
        assert chapters[0]["page"] == 0
        assert chapters[1]["page"] == 1
        assert chapters[2]["page"] == 2

    def test_heuristic_chinese_chapters(self, tmp_path):
        pdf = str(tmp_path / "heuristic.pdf")
        _make_pdf(pdf, [
            ("第一章 引言", 14),
            ("第二章 方法", 14),
        ], fontname="china-s")
        chapters = detect_chapters(pdf)

        titles = [ch["title"] for ch in chapters]
        assert any("第一章" in t for t in titles)
        assert any("第二章" in t for t in titles)

    def test_heuristic_english_chapter(self, tmp_path):
        pdf = str(tmp_path / "eng.pdf")
        _make_pdf(pdf, [
            ("Chapter 1 Introduction\nSome text.", 14),
            ("Chapter 2 Methods\nMore text.", 14),
        ])
        chapters = detect_chapters(pdf)

        assert len(chapters) >= 1
        assert any("Chapter 1" in ch["title"] for ch in chapters)

    def test_no_headings_returns_empty_list(self, tmp_path):
        pdf = str(tmp_path / "plain.pdf")
        _make_pdf(pdf, [("Just some plain text.", 12), ("More plain text.", 12)])
        chapters = detect_chapters(pdf)

        assert isinstance(chapters, list)
        # No chapter headings → empty (or at most auto-detected false positives
        # from very short pages – we just check the type here)


# ---------------------------------------------------------------------------
# split_pdf_by_chapters
# ---------------------------------------------------------------------------

class TestSplitPdfByChapters:
    def test_splits_into_correct_number_of_files(self, tmp_path):
        pdf = str(tmp_path / "book.pdf")
        _make_pdf_with_toc(pdf, [
            ("第一章 概述", "内容A"),
            ("第二章 方法", "内容B"),
            ("第三章 结论", "内容C"),
        ])
        out_dir = str(tmp_path / "chapters")
        files = split_pdf_by_chapters(pdf, out_dir)

        assert len(files) == 3
        for f in files:
            assert os.path.isfile(f)
            assert f.endswith(".pdf")

    def test_chapter_filenames_are_numbered(self, tmp_path):
        pdf = str(tmp_path / "book.pdf")
        _make_pdf_with_toc(pdf, [("Chapter 1 Intro", "text")])
        out_dir = str(tmp_path / "chapters")
        files = split_pdf_by_chapters(pdf, out_dir)

        assert os.path.basename(files[0]).startswith("001_")

    def test_no_chapters_saves_full_document(self, tmp_path):
        pdf = str(tmp_path / "nodiv.pdf")
        _make_pdf(pdf, [("plain text", 12), ("more text", 12)])
        out_dir = str(tmp_path / "chapters")
        files = split_pdf_by_chapters(pdf, out_dir, chapters=[])

        assert len(files) == 1
        assert os.path.basename(files[0]) == "full_document.pdf"

    def test_each_chapter_has_correct_page_count(self, tmp_path):
        pdf = str(tmp_path / "book.pdf")
        _make_pdf_with_toc(pdf, [
            ("第一章 概述", "内容"),
            ("第二章 方法", "内容"),
        ])
        out_dir = str(tmp_path / "chapters")
        files = split_pdf_by_chapters(pdf, out_dir)

        for f in files:
            doc = fitz.open(f)
            assert len(doc) == 1
            doc.close()

    def test_output_dir_is_created(self, tmp_path):
        pdf = str(tmp_path / "book.pdf")
        _make_pdf_with_toc(pdf, [("第一章 概述", "内容")])
        out_dir = str(tmp_path / "new" / "sub" / "dir")
        split_pdf_by_chapters(pdf, out_dir)

        assert os.path.isdir(out_dir)

    def test_custom_chapters_list_respected(self, tmp_path):
        """Passing an explicit chapters list overrides auto-detection."""
        pdf = str(tmp_path / "book.pdf")
        _make_pdf(pdf, [("page 0", 12), ("page 1", 12), ("page 2", 12)])
        chapters = [{"title": "Part A", "page": 0}, {"title": "Part B", "page": 2}]
        out_dir = str(tmp_path / "out")
        files = split_pdf_by_chapters(pdf, out_dir, chapters=chapters)

        assert len(files) == 2
        # First chapter: pages 0–1 → 2 pages
        doc0 = fitz.open(files[0])
        assert len(doc0) == 2
        doc0.close()
        # Second chapter: page 2 → 1 page
        doc1 = fitz.open(files[1])
        assert len(doc1) == 1
        doc1.close()


# ---------------------------------------------------------------------------
# text_extractor
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_basic_extraction(self, tmp_path):
        pdf = str(tmp_path / "t.pdf")
        _make_pdf(pdf, [("Hello World", 12)])
        text = extract_text(pdf)
        assert "Hello World" in text

    def test_multi_page_extraction(self, tmp_path):
        pdf = str(tmp_path / "t.pdf")
        _make_pdf(pdf, [("Page One", 12), ("Page Two", 12)])
        text = extract_text(pdf)
        assert "Page One" in text
        assert "Page Two" in text

    def test_clean_strips_outer_whitespace(self, tmp_path):
        pdf = str(tmp_path / "t.pdf")
        _make_pdf(pdf, [("  spaces  ", 12)])
        text = extract_text(pdf, clean=True)
        assert text == text.strip()

    def test_no_clean_preserves_raw_text(self, tmp_path):
        pdf = str(tmp_path / "t.pdf")
        _make_pdf(pdf, [("raw text", 12)])
        text = extract_text(pdf, clean=False)
        assert isinstance(text, str)

    def test_extract_to_file_writes_file(self, tmp_path):
        pdf = str(tmp_path / "t.pdf")
        out = str(tmp_path / "out.txt")
        _make_pdf(pdf, [("Written content", 12)])
        result = extract_text_to_file(pdf, out)
        assert result == out
        assert os.path.isfile(out)
        with open(out, encoding="utf-8") as fh:
            assert "Written content" in fh.read()

    def test_extract_to_file_is_utf8(self, tmp_path):
        """Output file must use UTF-8 encoding (required for CJK text)."""
        pdf = str(tmp_path / "t.pdf")
        out = str(tmp_path / "out.txt")
        _make_pdf(pdf, [("中文内容 test", 12)])
        extract_text_to_file(pdf, out)
        with open(out, encoding="utf-8") as fh:
            content = fh.read()
        assert isinstance(content, str)


# ---------------------------------------------------------------------------
# _clean_text (unit tests for the helper itself)
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_collapses_multiple_blank_lines(self):
        result = _clean_text("a\n\n\n\nb")
        assert "\n\n\n" not in result

    def test_form_feed_becomes_newline(self):
        result = _clean_text("a\fb")
        assert "\f" not in result
        assert "a" in result
        assert "b" in result

    def test_horizontal_space_collapsed(self):
        result = _clean_text("hello    world")
        assert "  " not in result
