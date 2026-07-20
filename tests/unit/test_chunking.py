import pytest

from src.services.chunking import TextChunker


def test_split_preserves_content_with_overlap() -> None:
    chunks = TextChunker(size=100, overlap=20).split("word " * 80, {"category": "test"})
    assert len(chunks) > 1
    assert all(chunk.text and chunk.metadata["category"] == "test" for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        TextChunker(size=100, overlap=100)

