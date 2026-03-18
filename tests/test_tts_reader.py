"""
Unit tests for tts_reader.py helper functions that do NOT require
a network connection (edge-tts API calls are not exercised here).
"""

from src.tts_reader import _split_text


class TestSplitText:
    def test_short_text_not_split(self):
        text = "短文本不需要分割。"
        chunks = _split_text(text, max_chars=100)
        assert chunks == [text]

    def test_long_text_split_into_multiple_chunks(self):
        # Build a text longer than max_chars using repeated sentences.
        sentence = "这是一个测试句子。"
        text = sentence * 20          # 180 chars
        chunks = _split_text(text, max_chars=50)
        assert len(chunks) > 1
        assert all(len(c) <= 50 + len(sentence) for c in chunks)  # near limit

    def test_chunks_reconstruct_original(self):
        sentence = "Hello world. "
        text = sentence * 30
        chunks = _split_text(text, max_chars=80)
        assert "".join(chunks) == text

    def test_single_huge_sentence_stays_together(self):
        """A sentence longer than max_chars must not be discarded."""
        text = "A" * 200
        chunks = _split_text(text, max_chars=50)
        # All content must be preserved
        assert "".join(chunks) == text

    def test_english_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        chunks = _split_text(text, max_chars=20)
        assert len(chunks) > 1
        assert "".join(chunks) == text

    def test_empty_string(self):
        chunks = _split_text("", max_chars=100)
        assert chunks == [""]
